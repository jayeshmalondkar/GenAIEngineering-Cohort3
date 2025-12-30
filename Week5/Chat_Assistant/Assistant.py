import json
from typing import List, Dict, Any
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import lancedb
import openai
import groq
from dotenv import load_dotenv
import re
from google import genai
from google.genai import types
from urllib.parse import urlparse

# Text splitter functionality is provided by LangChain framework
from langchain_text_splitters import HTMLHeaderTextSplitter, RecursiveCharacterTextSplitter

# Make use of BS for hadling the web content
import requests
from bs4 import BeautifulSoup
from Web_Scraper import fetch_main_content

# Globals
Embedder_1 = SentenceTransformer ("sentence-transformers/all-MiniLM-L6-v2")
Embedder_2 = SentenceTransformer ("sentence-transformers/all-mpnet-base-v2")

# Initialise an client object with API key
load_dotenv ()
Retrieval_Client = groq.Groq ()
Gen_Client = genai.Client()

# Create a Lance DB Vector Base
DB = lancedb.connect ('Quick_Ref')

def get_main_content (url, type):

    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    # Remove layout elements
    for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()

    # Check and get main section of the pages
    main = soup.find("main")

    if not main:
        
        # fallback method, if no 'main' section in html page
        candidates = soup.find_all("div", recursive=True)
        main = max(candidates, key=lambda c: len(c.get_text(strip=True)), default=soup.body)

    # Get cleaned HTML content. Tags retained
    main_html = str(main)

    # If HTML content is required, provide with the tags
    if type == 'html':
        return (main_html)

    # If text is requirred, provide only the text content
    elif type == 'text':

        text_soup = BeautifulSoup (main_html, "html.parser")
        main_text = text_soup.get_text(separator="\n", strip=True)
        return main_text

def meta_data_from_headings (heading: dict, n: int = 1, from_end: bool = True, sep: str = " : ") -> str:
    """
    Concatenates n values from a heading dictionary, either from the start or from the end.

    Param:
        heading (dict): Input dictionary for headings.
        n (int): Number of elements to take.
        from_end (bool): If True, take from the end; else from the start.
        sep (str): Optional separator to use between concatenated strings.

    Returns: Meta data as concatenation of headings.
    """
    values = list(heading.values())

    if n <= 0:
        n = 1
    if n > len(values):
        n = len(values)

    # Select n items from start or end
    selected = values[-n:] if from_end else values[:n]

    # Always concatenate in forward direction
    return sep.join(str(v) for v in selected)

def Build_Chunks (url, source, chunk_size_limit = 500, chunk_size=300):

    # Define what are the splitters to be considered. There is default in library itself
    seperators = [".", "?", "!"]

    # Splitter function based on seperator and the length criteria
    text_splitter = RecursiveCharacterTextSplitter (chunk_size=chunk_size, chunk_overlap=0,
                                                    length_function=len, is_separator_regex=False,
                                                    keep_separator=False,
                                                    separators=seperators,
                                                    )

    # levels of header tags in html to split on
    header_levels = [
        ("h1", "Header 1"),
        ("h2", "Header 2"),
        ("h3", "Header 3"),
        ("h4", "Header 4"),
    ]

    # Define a Splitter object for HTML content from the lib
    # This library also gives splitter for Markdown, JSON etc
    html_splitter = HTMLHeaderTextSplitter(header_levels)    

    # Get the main content
    # HTML_Content = get_main_content (url, "html")
    HTML_Content, Full_Content = fetch_main_content (url)
    print ("Robust")

    # Chunk based on document structure
    docs = html_splitter.split_text (HTML_Content)

    # Start with empty list
    Chunks = []

    with open ('chunks.txt', mode='w') as f:

        for doc in docs :

            try :

                meta_data = meta_data_from_headings (doc.metadata)

                if not meta_data:
                    meta_data = 'Generic'

                # If the chunk is too long,
                if (len(doc.page_content) > chunk_size_limit):

                    # Split by sentece(s) by shorter lenth
                    splits = text_splitter.split_text(doc.page_content)

                    # Make them individual chunk with same meta data
                    for split in splits:

                        # Capture if the meta data and text are not the same
                        if (meta_data != split):

                            Chunk = {'source': source,'topic' : meta_data, 'text' : split}
                            print (Chunk, "\n----",file=f)

                            Chunks = Chunks + [Chunk]
                        
                else :
                    
                    if (meta_data != doc.page_content):
                        
                        Chunk = {'source': source, 'topic' : meta_data, 'text' : doc.page_content}
                        print (Chunk, "\n----",file=f)
                        Chunks = Chunks + [Chunk]
                
            except Exception :
                pass

    print (len(Chunks))
    nb_chunks = len(Chunks)

    return nb_chunks, Chunks

def Capture_Knowledge (url : str, table_name : str) -> dict[str, str] :

    # Default Error Code
    Ret_Val = {'Status' : "Erorr Processing"}

    parsed = urlparse(url)
    Source = parsed.netloc

    # Generate Chunks from the website main content
    nb_chunks, Chunks = Build_Chunks (url, Source)

    # If there are no chunks, probably error getting the content
    if nb_chunks <= 0 :
        Ret_Val ['Status'] = "No content at source"
    
    else:
        
        # Create vectors and store in the Chunks 
        for idx, Chunk in enumerate (Chunks):

            vector = Embedder_1.encode (Chunk['text'])
            Chunks[idx]['vector'] = vector.tolist ()
        
        # Create a Table and add the Chunks data
        table = DB.create_table(table_name, data=Chunks, mode="overwrite") 
        # print (table.schema)

        # Status
        Ret_Val ['Status'] = "Knowledge Captured"
        Ret_Val ['Num_Chunks'] = str (nb_chunks)
        Ret_Val ['Source'] = Source
    
    return Ret_Val

# Query transformation (LLM + fallback)
def transform_query (query: str, n_paraphrases: int = 3) -> List[str]:
    prompt = (
        'You are given a user query. With that, produce:\n'
        f'1) a precise reformulation suitable for content retrieval ("precise")\n'
        f'2) {n_paraphrases} concise paraphrases of the original query suitable for semantic retrieval ("paraphrases")\n'
        'Return JSON with keys: "precise" (string) and "paraphrases" (list of strings). No additional Text\n'
        'User query: ' + query
    )

    messages=[
    {
        "role": "user",
        "content": prompt,
    }
    ]
    completion = Retrieval_Client.chat.completions.create(
        messages=messages,    
        model="llama-3.3-70b-versatile",
        # model="openai/gpt-oss-120b",
        temperature=0.0,
        stop=None,
    )

    # print (completion.choices[0].message.content)

    clean_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", completion.choices[0].message.content)
    data = json.loads (clean_str)
    texts = [data["precise"]] + data["paraphrases"]

    return texts

def expand_query (query: str, n_alternates: int = 3) -> List[str]:
    prompt = (
        f'Generate {n_alternates} diverse query variations that can expand search horizon, but preserve intent of the following user query:\nQuery: {query}\n'
        'Return JSON with keys: "alternates" (list of strings). No additional Text\n'
        'User query: ' + query
    )

    messages=[
    {
        "role": "user",
        "content": prompt,
    }
    ]
    completion = Retrieval_Client.chat.completions.create(
        messages=messages,    
        model="llama-3.3-70b-versatile",
        # model="openai/gpt-oss-120b",
        temperature=0.0,
        stop=None,
    )

    # print (completion.choices[0].message.content)

    clean_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", completion.choices[0].message.content)
    data = json.loads (clean_str)
    texts = data["alternates"]

    return texts

def Retrieve_Context (Query, table_name) :

    # RAG Fusion
    trans_queries = transform_query (Query)
    expand_queries = expand_query (Query)

    queries  = trans_queries + expand_queries

    Context = []
    table = DB.open_table (table_name)

    for query in queries :

        Query_Vector = Embedder_1.encode (query).tolist ()
        Results = table.search(Query_Vector).distance_type("cosine").distance_range(upper_bound=0.6).limit(5).to_list ()

        # print (len (Results))

        Text_List = [r['text'] for r in Results]
        Context = Context + Text_List

    Context = list(set(Context))
    print (len(Context))

    return Context

def Ask_Assistant (Chat_Hist: str, Query : str, table_name : str) -> str:
    
    # Instruction for the LLM
    # Instruction = """You are given context information and a user query. You have to provide detailed answer to user query based on information provided in context.
    #                 Provide an informative answer to the user query **BASED** on the context.
    #                 If sufficient details are not in context, respond as "No Sufficient Details"
    #            """

    Gr_Instruction = """You are given context information, Chat history and a user query. 
                    Formulate a elaborative answer to user query based on the context provided and in continuation to the chat history.
                    Provide answer ONLY based on history and context.
                """

    Gm_Instruction = """ You are an helpful assitant who can answer to user's query with great detail.
                    You are given chat history, a context information and a user query.                     
                    
                    Follow the steps :
                    1. Understand User Query clearly
                    2. Understand the chat history so far and the details provided in the context
                    3. See if there are enough details avaiable in context to answer the question
                    4. Formulate a elaborative answer in a creative way to the question based on the context provided and in continuation to the history.

                    Don't sound like you are referring a context or instructions. **Respond Naturally**.                 
                    Answer in Marked Down Text format.
                """

    # Get context from Knowledge base
    Context = Retrieve_Context (Query, table_name)

    messages=[
    {
        "role": "system",
        "content": Gr_Instruction,
    },
    {
        "role": "user",
        "content": "Chat History : \n"+Chat_Hist,
    },
    {
        "role": "user",
        "content": "Context : \n"+str(Context),
    },    
    {
        "role": "user",
        "content": "User Query : \n"+Query,
    },    

    ]

    # Invoke from Groq
    # completion = Retrieval_Client.chat.completions.create(
    #     messages=messages,    
    #     # model="llama-3.3-70b-versatile",
    #     model="openai/gpt-oss-120b",
    #     # temperature=0.0,
    #     stop=None,
    # )
    # return completion.choices[0].message.content

    # Invoke Gemini
    response = Gen_Client.models.generate_content(
                    model="gemini-2.0-flash",
                    config =types.GenerateContentConfig(
                                system_instruction=Gm_Instruction,
                                # temperature=0.0
                                ),
                    contents = ["Chat History : \n"+Chat_Hist, "Context : \n"+str(Context), "User Query : \n"+Query]
    )

    return response.text
