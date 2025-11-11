# import all necessary module 

from langgraph.graph import StateGraph,START,END
from typing import TypedDict,Annotated,Literal
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from dotenv import load_dotenv
from pydantic import BaseModel, Field,field_validator
import operator
import os
from langchain_core.messages import HumanMessage,SystemMessage
import time
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langsmith import traceable
from datetime import datetime
from langchain_core.tools import tool
import smtplib
from email.mime.text import MIMEText
import requests
from src.linkdin.linked_post import linked_post_fun
from src.kundan.supabase_get.app import main
from fastapi import FastAPI
from src.email_send.email_calender import send_interview_invites
import re

#set up the openAi model 
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# LLM that generates the post (creative)
generator_llm = ChatOpenAI(api_key=api_key, model="gpt-4o")  # powerful & balanced

# LLM that evaluates the post (analytical)
evaluator_llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini")  # faster, cheaper, less creative

# LLM that optimizes/updates the post (refinement focus)
optimizer_llm = ChatOpenAI(api_key=api_key, model="gpt-4-turbo")  # efficient reasoning

# LLM that extracts info (resume-related)
resume_llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini")  # compact, ideal for extraction

#embedding model 
emb_model=OpenAIEmbeddings(model='text-embedding-3-small')
# Linkdin api url 
url = os.getenv("URL")

#define the state
class Jd(TypedDict):
    topic : Annotated[str,Field(description="here we give the topic of JD")]
    tweet: Annotated[str,Field(description="Here llm gives us the JD")]
    evaluation: Literal["approved", "needs_improvement"]
    feedback: str
    post_status: str
    iteration: int
    max_iteration: Annotated[int,Field(description="max no iteration ")]
    tweet_history: Annotated[list[str], operator.add]
    feedback_history: Annotated[list[str], operator.add]
    min_no_cv_you_want:int
    min_no_days_you_want_to_collect_cv:int
    Cv_requirement:Annotated[str,Field(description="check enough cv or not")]
    Cv_history:Annotated[list[str],operator.add]
    full_cv:Annotated[list[str],operator.add]
    retry_cv:int
    max_retry_cv:int
    selected_student_for_interview:Annotated[list[dict],operator.add]
    no_of_student_you_want_for_interview:Annotated[int,Field(description="no of student you want to select for interview")]
    #human_permission_for_interview:Annotated[str,Field(description="please select the interview date")]
    interview_date:Annotated[str,Field(description="here we select the interview date for student")]
    interview_time:Annotated[str,Field(description="here we select the interview time for student")]
    mail_generated_for_selected_students:Annotated[list[dict],operator.add]
    #mails_sent:Annotated[list[str],operator.add]
    interview_invite_status:list


#Jd store here 
jd=[]

#pydantic schema for the output of evaluation node
class output_schema(BaseModel):
    evaluation:Literal["approved", "needs_improvement"]= Field(..., description="Final evaluation result.")

    feedback:Annotated[str,Field(..., description="feedback for the tweet.")]


#pydantatic schema for resume 
class OutputStructure(BaseModel):
    name: Annotated[str, Field(description="Full name of the student")]
    phone: Annotated[str, Field(description="Phone number of the student")]
    email:Annotated[str,Field(description="Email address of the student ")]
    summary: Annotated[str, Field(description="Summary of the resume within 100 words")]
    full_cv:Annotated[str,Field(description="Give a clean  text for the Full CV which represent the student CV like score,Skill,Project ")]

resume_output_llm=resume_llm.with_structured_output(OutputStructure)

#define the jd_generation node
@traceable(name="Generate Jd", tags=["dimension:language"], metadata={"dimension": "language"})
def jd_genearation(state:Jd)->Jd:
    message=[
        SystemMessage(content="you are a post genrator for a particular job topic"),
        HumanMessage(content=f"generate a job description on this topic {state['topic'] } within 100 words you also given company name ,location ")
    ]
    try:
        response=generator_llm.invoke(message).content
    except Exception as e:
        raise Exception("LLM call fail")

    return {"tweet":response,"tweet_history":[response]}


# define the evaluation node
structured_evaluator_llm = evaluator_llm.with_structured_output(output_schema)

@traceable(name="evaluate_Jd", tags=["dimension:Analysis"], metadata={"dimension": "Analysis the tweet"})
def jd_evaluation(state:Jd)->Jd:
    query=f"Evaluate this job discription {state['tweet']} for this topic {state['topic']} and give a feedback "
    try:
        response=structured_evaluator_llm.invoke(query)
    except Exception as e:
        raise Exception("run time error ")
        

    return {"evaluation":response.evaluation,"feedback":response.feedback,"feedback_history":[response.feedback]}
    


# define jd_update node

@traceable(name="Update Jd", tags=["dimension:optimize"], metadata={"dimension": "optimize the tweet "})
def optimize_tweet(state:Jd):

    messages = [
        SystemMessage(content="You punch up tweets for virality and humor based on given feedback."),
        HumanMessage(content=f"""
Improve the tweet based on this feedback:
"{state['feedback']}"

Topic: "{state['topic']}"
Original Tweet:
{state['tweet']}

Re-write it as a short, viral-worthy tweet. Avoid Q&A style and stay under 280 characters.
""")
    ]

    response = optimizer_llm.invoke(messages).content
    iteration = state['iteration'] + 1

    return {'tweet': response, 'iteration': iteration, 'tweet_history': [response]}




#--------------------------------------Conditional node for JD update --------------------------------------------------
@traceable(name="Conditional Node for Jd", tags=["dimension:decision"], metadata={"dimension": "decision to go back to Optimize or not"})
def route_evaluation(state:Jd):

    if state['evaluation'] == 'approved' or state['iteration'] >= state['max_iteration']:
        jd.append(state["tweet"])
        return 'approved'
    else:
        return 'needs_improvement'
    

#----------------------------------Pydantic for posting job description--------------------------------------------
class JobPosting(BaseModel):
    job:Annotated[str,Field(...,description='give job discription in 100 word and for this job description  ask applicants to apply on this link "http://51.21.221.225:8501"')]
link_llm=generator_llm.with_structured_output(JobPosting)


#----------------------Post Jd in Linkdin--------------------------------------------------------------------

@traceable(name="Post JD on LinkedIn", tags=["dimension:Post"], metadata={"dimension": "post job on LinkedIn"})
def post_in_linkdin(state:Jd):
    clean_text = re.sub(r"\*", "", state["tweet"])
    prompt = f"Here is the job description {state['tweet']}"  # FIXED: changed state["tweet"] to state['tweet']
    text = link_llm.invoke(prompt)
    linked_post_fun(text.job, url)
    return {"post_status": "successful"}


#-------------------------------------------cv check node--------------------------------------------------------
@traceable(name="Check_no_of_cv", tags=["dimension:Count CV"], metadata={"dimension": "Count no of application"})
def check_cvs(state: Jd) -> Jd:

    # folder_path = "allpdfs"  # your CV folder

    #waiting for some time 
    wait = state["min_no_days_you_want_to_collect_cv"]
    print(f"waiting for {wait} seconds")  # FIXED: removed extra quote
    time.sleep(wait) 
    main()
    folder_path = "allpdfs"

    pdf_files = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
    # #num_pdfs = len(pdf_files)

    # # print(f"Found {num_pdfs} resumes")
    # #waiting for some time 
    # wait=60
    # print(f"waiting for {wait} seconds")
    # time.sleep(wait) 

    #check  no of CV after waiting for some 
    num_pdfs = len(pdf_files)
    print(f"Found {num_pdfs} resumes")  # FIXED: removed extra quote


    retry_cv = state["retry_cv"] + 1

    if num_pdfs < state["min_no_cv_you_want"]:
        print(f"Less than {state['min_no_cv_you_want']} resumes found.So we  Waiting for {wait} seconds again ...")  # FIXED: changed state["min_no_cv_you_want"] to state['min_no_cv_you_want']
        return {"Cv_requirement": "needs_more_resumes", "retry_cv": retry_cv}  # temporary signal
    else:
        return {"Cv_requirement": "enough_resumes", "retry_cv": 0}
    

#---------------------------conditional node to check no of CV enough or not---------------------------------------

@traceable(name="Check_enough_Cv_or_not", tags=["dimension:Enough Cv"], metadata={"dimension": "Enough Cv or not"})
def conditional_cv(state:Jd)->Jd:
    if state["Cv_requirement"] == "needs_more_resumes" and state["retry_cv"] < state["max_retry_cv"]:
        return "needs_more_resumes"
    elif state["Cv_requirement"] == "enough_resumes":
        return "enough_resumes"
    else:
        return "stop_checking"


#------------------------Nodes for collect CV and then store the metadata of CV into database and summary into state---------------
import sqlite3
@traceable(name="Summarize Cv", tags=["dimension:CV extract"], metadata={"dimension": "We collect the CV text "})
def summarize_cv(state: Jd) -> Jd:
    folder_path = "allpdfs"
    pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(".pdf")]
    summary_history = []
    full_cv = []
    db_path = "resumes.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("🧹 Old database deleted successfully.")
    # --- Setup SQLite connection ---
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT UNIQUE,   -- make email unique
        summary TEXT,
        full_cv TEXT
    )
    """)
    
    for pdf in pdf_files:
        loader = PyPDFLoader(pdf)
        docs = loader.load()
        text = " ".join([doc.page_content for doc in docs])
        
        query = f"""
Extract the following information from this resume:
1. Full name of the student
2. Phone number (if available)
3. Email of the student
4. A summary of the resume (within 100 words)
5.A clean text for the entire CV 

Resume text:
{text}
"""
        response = resume_output_llm.invoke(query)

        # Save summary in state
        summary_history.append(response.summary)
        full_cv.append(response.full_cv)

        # --- Check if email already exists ---
        cursor.execute("SELECT id FROM candidates WHERE email = ?", (response.email,))
        existing = cursor.fetchone()
        
        if not existing:  # only insert if not found
            cursor.execute("""
            INSERT INTO candidates (name, phone, email, summary,full_cv) VALUES (?, ?, ?, ?,?)
            """, (response.name, response.phone, response.email, response.summary, response.full_cv))
    
    # Commit and close DB connection
    conn.commit()
    conn.close()

    return {"Cv_history": summary_history, "full_cv": full_cv}

    

#--------------------------------------define embedding and retrival node--------------------------------------------- 

@traceable(name="Retrive CV ", tags=["dimension:Retrive CV"], metadata={"dimension": "Here we retrive Student for the Job"})
def embedding_cv(state: Jd) -> Jd:
    # --- Load candidates from DB ---
    conn = sqlite3.connect("resumes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone, email, summary,full_cv FROM candidates")
    rows = cursor.fetchall()
    conn.close()

    #check if any student apply or not 
    if not rows:
        print("No candidates in DB to index.")
        return {"selected_student_for_interview": []}

    # Convert DB rows → Documents with metadata
    docs = [
        Document(
            page_content=row[4],  # full cv
            metadata={
                "name": row[0],
                "phone": row[1],
                "email": row[2]
            }
        )
        for row in rows
    ]

    # Build FAISS index
    vs = FAISS.from_documents(docs, emb_model)
    vs.save_local("faiss_index")

    retriever = vs.as_retriever(search_type="similarity", search_kwargs={"k": state["no_of_student_you_want_for_interview"]})
    results = retriever.invoke(state["tweet"])  # query with JD/tweet

    # Extract metadata of top matches
    top_matches = [
        {
            "name": doc.metadata.get("name"),
            "email": doc.metadata.get("email"),
            "phone": doc.metadata.get("phone"),
            #"matched_summary": doc.page_content
        }
        for doc in results
    ]

    return {"selected_student_for_interview": top_matches}


#---------------------------------------Pydantic schema for mail genration 
class MailGeneration(BaseModel):
    mail_generated:Annotated[str,Field(..., description="for the given name and job description generate a email for the  interview ")]
email_llm=generator_llm.with_structured_output(MailGeneration)



#------------------------mail sending tool-----------------------------------------------------------------------
def send_interview_nodes(state):
    selected_students = state["selected_student_for_interview"]
    job_description = state["tweet"]
    interview_date = state["interview_date"]
    interview_time = state["interview_time"]

    result = send_interview_invites(selected_students, job_description, email_llm, interview_date, interview_time)
    return {"interview_invite_status": result}




#-----------------------------------------------create the graph------------------------------------------------------
graph = StateGraph(Jd)
# add nodes 
# ============================
# 🔹 Add Nodes
# ============================
graph.add_node("jd_genearation", jd_genearation)
graph.add_node("jd_evaluation", jd_evaluation)
graph.add_node("optimize_tweet", optimize_tweet)
graph.add_node("check_cvs", check_cvs)
graph.add_node("summarize_cv", summarize_cv)
graph.add_node("embedding_cv", embedding_cv)
# graph.add_node("mail_generated_llm", mail_generated_llm)
# graph.add_node("fix_date_time", fix_date_time)
graph.add_node("post_in_linkdin", post_in_linkdin)
graph.add_node("send_interview_nodes", send_interview_nodes)
# graph.add_node("send_mails_node", send_mails_node)


# ============================
# 🔹 Add Edges (Flow Connections)
# ============================

# --- JD generation and evaluation ---
graph.add_edge(START, "jd_genearation")
graph.add_edge("jd_genearation", "jd_evaluation")

# --- Conditional after JD evaluation ---
# ✅ If approved → post on LinkedIn first
# ✅ If needs improvement → go to optimization loop
graph.add_conditional_edges(
    "jd_evaluation",
    route_evaluation,
    {
        "approved": "post_in_linkdin",
        "needs_improvement": "optimize_tweet"
    }
)

# --- Retry loop for improvement ---
graph.add_edge("optimize_tweet", "jd_evaluation")

# --- After posting on LinkedIn, move to CV checking ---
graph.add_edge("post_in_linkdin", "check_cvs")

# --- Conditional flow for CV checking ---
graph.add_conditional_edges(
    "check_cvs",
    conditional_cv,
    {
        "enough_resumes": "summarize_cv",
        "needs_more_resumes": "check_cvs",
        "stop_checking": "summarize_cv"
    }
)

# --- Continue through CV summarization and embedding ---
graph.add_edge("summarize_cv", "embedding_cv")
graph.add_edge("embedding_cv", "send_interview_nodes")
graph.add_edge("send_interview_nodes", END)

# --- Optional (if you later include mail pipeline) ---
# graph.add_edge("fix_date_time", "mail_generated_llm")
# graph.add_edge("mail_generated_llm", END)
# graph.add_edge("send_mails_node", END)




workflow = graph.compile()





# print(result["feedback"])
# # print(result["tweet"])
# print("selected students:",result['selected_student_for_interview'])
# print("mail_histroy",result["mail_generated_for_selected_students"])


# #------------------------add API--------------------------------------------------------------------------------
# from fastapi import FastAPI
# app=FastAPI()

# @app.post("/predict")
# def comlplete_workflow():
#     initial_state = {
#     "topic": "generate Job description for my company name Laxmi chect fund ,For this topic Data science ,with required skill,python,Mlops,ML,DL",
#     "iteration": 0,
#     "max_iteration": 5,
#     "retry_cv":0,
#     "max_retry_cv":3,
#     "min_no_cv_you_want":1
#     }
#     result = workflow.invoke(initial_state)
#     return {"result":result}


#-------------------------------------Offerletter Workflow after interview-------------------------------------------
class OfferLetter(TypedDict):
    candidate:list[dict]
    role:Annotated[str,Field(...,description="Give the role the candidate selected ")]
    salary:str

from src.email_send.send_offers import send_offers
def send_offer_letter(state:OfferLetter):
    return send_offers(state["candidate"], state["role"], state["salary"])



Offerlatergraph = StateGraph(OfferLetter)

Offerlatergraph.add_node("send_offer_letter", send_offer_letter)


Offerlatergraph.add_edge(START, "send_offer_letter")
Offerlatergraph.add_edge("send_offer_letter", END)


offerlaterworkflow = Offerlatergraph.compile()