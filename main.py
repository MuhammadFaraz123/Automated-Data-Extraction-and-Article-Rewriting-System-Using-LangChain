from typing import Union, List, Dict, Optional, Any
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel, Field  
from langchain.llms import OpenAI
from pydantic import BaseModel, validator
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
import tiktoken
import os
import openai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils import prettify_exec_info
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv  

load_dotenv()  

# load your api key here
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Define model
model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.0)

graph_config = {
   "llm": {
      "api_key": openai.api_key,
      "model": "openai/gpt-4o-mini",
   },
}

# Database Schema
# PostgreSQL connection setup
def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    return conn

# Function to create tables if they don't exist
def create_tables_if_not_exist(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subupdates (
            id SERIAL PRIMARY KEY,
            organization TEXT,
            role TEXT,
            instrument TEXT,
            amount FLOAT,
            financing_structure TEXT
        );
        CREATE TABLE IF NOT EXISTS project (
            id SERIAL PRIMARY KEY,
            title TEXT,
            project_status TEXT,
            technology_and_grid_system TEXT,
            type_of_installation TEXT,
            grid_type TEXT,
            pv_size FLOAT
        );
        CREATE TABLE IF NOT EXISTS organization (
            id SERIAL PRIMARY KEY,
            name TEXT,
            website_link TEXT,
            role TEXT
        );
        CREATE TABLE IF NOT EXISTS updates (
            id SERIAL PRIMARY KEY,
            title TEXT,
            news_update_type TEXT,
            receiver_category TEXT,
            text_of_article TEXT,
            receiver_country TEXT[],
            date TEXT,
            total_amount FLOAT
        );
        """)
    conn.commit()


# Function to insert subUpdates data into the 'subupdates' table
def insert_sub_updates(conn, sub_updates):
    try:
        with conn.cursor() as cursor:
            for sub_update in sub_updates:
                cursor.execute(
                    """
                    INSERT INTO subupdates (organization, role, instrument, amount, financing_structure)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (sub_update['organization'], sub_update['role'], sub_update['instrument'], sub_update['amount'], sub_update['financingStructure'])
                )
        conn.commit()
    except Exception as e:
        print(f"Error inserting subUpdates: {e}")

# Function to insert project-specific data into the 'project' table
def insert_project_data(conn, extracted_data):
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO project (title, project_status, technology_and_grid_system, type_of_installation, grid_type, pv_size)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (extracted_data['title'], extracted_data['projectStatus'], extracted_data['technologyAndGridSystem'],
                 extracted_data['typeOfInstallation'], extracted_data['gridType'], extracted_data['pvSize'])
            )
        conn.commit()
    except Exception as e:
        print(f"Error inserting project data: {e}")

# Function to insert organization-specific data into the 'organization' table
def insert_organization_data(conn, extracted_data):
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO organization (name, website_link, role)
                VALUES (%s, %s, %s);
                """,
                (extracted_data['organizationFinanced']['name'], extracted_data['organizationFinanced'].get('website', None), extracted_data['organizationFinanced']['role'])
            )
        conn.commit()
    except Exception as e:
        print(f"Error inserting organization data: {e}")

# Function to insert other data into the 'updates' table
def insert_update_data(conn, extracted_data):
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO updates (title, news_update_type, receiver_category, text_of_article, receiver_country, date, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    extracted_data['title'], 
                    extracted_data['newsUpdateType'], 
                    extracted_data['receiverCategory'], 
                    extracted_data['textOfArticle'],
                    '{' + ','.join(extracted_data['receiverCountry']) + '}',
                    extracted_data['date'], 
                    extracted_data['totalAmount']
                )
            )
        conn.commit()
    except Exception as e:
        print(f"Error inserting update data: {e}")

#-----------DB Schema End-----------------

# Data models
class SubUpdate(BaseModel):  
    organization: str = Field()
    role: str = Field()
    instrument: Optional[str] = Field(None)
    amount: Union[float, int, None] = Field()
    financingStructure: Optional[str] = Field(None)

class ProjectFinanced(BaseModel):
    id: str = Field()
    name: str = Field()

class OrganizationFinanced(BaseModel):
    id: str = Field()
    name: str = Field()
    role: str = Field()

class ExtractedData(BaseModel):
    newsUrl: str = Field()
    title: str = Field()
    newsUpdateType: str = Field()
    receiverCategory: str = Field()  
    textOfArticle: str = Field()
    receiverCountry: str = Field()
    date: str = Field()
    projectFinanced: Optional[ProjectFinanced] = Field(None)  
    projectStatus: Optional[str] = Field(None) 
    projectStatusDate: Optional[str] = Field(None)  
    technologyAndGridSystem: Optional[str] = Field(None)
    typeOfInstallation: Optional[str] = Field(None)
    gridType: Optional[str] = Field(None)
    pvSize:  Union[float, int, None] = Field()
    organizationFinanced: Optional[OrganizationFinanced] = Field(None) 
    totalAmount: Union[float, int, None] = Field()
    subUpdates: List[SubUpdate] = Field()  

def get_json_schema(model: BaseModel):
    return model.json_schema()  

schema = ExtractedData.model_json_schema() 
parser = PydanticOutputParser(pydantic_object=ExtractedData)


# Prompt template
prompt = PromptTemplate(
    template="""
        Assume you are an expert in extracting data of solar power plants from articles.
        An article will be given as an input, and your task is to find and extract the following details from the article:

        - newsUrl: Link of the original article.
        - title: The title of the news article.
        - newsUpdateType: Categorize the news update as one of the following:
                                - Funding Update: Information about a project, organization, or entity receiving funding.
                                - M&A Update: Information about the acquisition or purchase of a project or organization.
                                - General Update: Any news update that does not fit into the funding or M&A categories.
                                - Other
        - receiverCategory: Indicates if the update pertains to a project or an organization:
                                - Project: A solar project that received investment from one or multiple organizations.
                                - Organization: An organization that received investment from one or multiple organizations.
                                - Other: Any recipient that does not fit into the project or organization categories.
        - textOfArticle: Give complete text of the article. should be more than 300 words.
        - receiverCountry: Should only mention name of the country. DONOT mention continent.
        - date: The date of the news update. Format should be "dd/mm/yyyy".
        - projectFinanced (appears only when recieverCategory is project): if recieverCategory is "Project" then give these details otherwise make it null.
                            Details include:
                                    - id: give random id.
                                    - name: usually structured as “Name Solar Project” or similar variants. If it is place by a
                                            company “mention the company name & size”.
                                    
        - projectStatus: appears only when receiver category is project otherwise make it null. if receiver category is not project and projectStatusDate is not found in the article then make it n/a. possible values are:
                                - Planning
                                - Commissioned
                                - Construction
                                - Operational
        - technologyAndGridSystem: appears only when receiver category is project otherwise make it null. possible values are:
                                - PV
                                - PV-Diesel-Storage Hybrid
                                - PV-Storage
                                - n/a (if data is not there)
        - typeOfInstallation: appears only when receiver category is project otherwise make it null. Possible values are:
                                - C&I
                                - Utility
                                - Mini-grid
                                - n/a (if data is not there)
        - gridType: appears only when receiver category is project otherwise make it null. Grid Type:
                                - On-grid
                                - Off-Grid
                                - n/a (if data is not there)
        - PV_Size: appears only when receiver category is project otherwise make it null. Amount with two digits in integer or float.

        - projectStatusDate: appears only when receiver category is project otherwise make it null. if receiver category is not project and projectStatusDate is not found in the article then make it n/a.
        - organizationFinanced: if recieverCategory is "Organization" then give these details otherwise make it null. Details include:
                                - id: give random id
                                - name: name of the organization that received the investment.
                                - role: role of the organization that received the investment. possible values are:
                                        - Government
                                        - Utility
                                        - Financing Vehicle
                                        - E-Mobility
                                        - PAYG SHS
        - totalAmmount: Total funding amount recieved, this should be an full amount figure.
        - subUpdates: Detailed updates about organizations, their roles, instruments, amounts, and financing structure.
                        - organization: The name of the party involved.
                        - role: The role of the party involved. Possible values are:
                                    - EPC Contractor
                                    - Financier
                                    - Supplier
                                    - Off-taker
                                    - Fund Manager
                                    - Owner
                        - instrument: The type of investment provided. Appears only when role is financier otherwise make it null. possible values are:
                                    - Debt
                                    - Grant
                                    - Equity
                        - amount: The amount of investment provided. Appears only when role is financier otherwise make it null.
                        - financingStructure: financingStructure should only mention if the role is of "Financier" otherwise make it null.
                   
        REMEMBER Sub-update can be more than one depending on the article or companies mentioned in the article. If role is not “Financier”, fields like instrument, amount, and financingStructure must be n/a.
        REMEMBER There is always one among projectFinanaced or organizationFinanaced, never two, never zero meaning that both projectFinanced and organizationFinanced cannot be null simultaneously.
        REMEMBER null is used when field does not apply, n/a is used when the information applies and information is not available.

        Your response should be formatted as a JSON instance that conforms to the JSON schema below.
        
        Here is the output schema:
        {format_instructions}

        Article:
        {query}
    """,
    input_variables=["query"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Function to chunk context
def chunk_text(text: str, max_tokens: int = 3000) -> List[str]:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    tokens = encoding.encode(text)
    chunks = [tokens[i:i + max_tokens] for i in range(0, len(tokens), max_tokens)]
    return [encoding.decode(chunk) for chunk in chunks]

# consolidate function
def consolidate_extracted_data(data_list: List[Dict]) -> Dict:
    consolidated = {}
    for data in data_list:
        for key, value in data.items():
            if key not in consolidated or not consolidated[key]:
                consolidated[key] = value
    return consolidated

# Function to extract data from an article for update
def generate_extracted_data(article: str) -> Dict:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    token_count = len(encoding.encode(article))
    
    if token_count > 12000:
        chunks = chunk_text(article)
        extracted_data_list = []
        
        for chunk in chunks:
            prompt_text = prompt.format(query=chunk)
            response = model(prompt_text)  
            if isinstance(response, AIMessage):  
                content = response.content  
            else:
                content = response  
            chunk_data = parser.parse(content) 
            extracted_data_list.append(chunk_data.dict())
        
        consolidated_data = consolidate_extracted_data(extracted_data_list)
        return consolidated_data
    else:
        prompt_text = prompt.format(query=article)
        response = model(prompt_text) 
        if isinstance(response, AIMessage): 
            content = response.content  
        else:
            content = response 
        extracted_data = parser.parse(content)
        return extracted_data.dict()

# Function to generate original text
def generate_original_text(article: str) -> Dict:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    token_count = len(encoding.encode(article))
    
    if token_count > 12000:
        chunks = chunk_text(article)
        extracted_data_list = []
        
        for chunk in chunks:
            prompt_text = prompt.format(query=chunk)
            response = model(prompt_text)  
            if isinstance(response, AIMessage):  
                content = response.content  
            else:
                content = response  
            chunk_data = parser.parse(content) 
            extracted_data_list.append(chunk_data.dict())
        
        consolidated_data = consolidate_extracted_data(extracted_data_list)
        return consolidated_data
    else:
        prompt_text = prompt.format(query=article)
        response = model(prompt_text) 
        if isinstance(response, AIMessage): 
            content = response.content  
        else:
            content = response 
        extracted_data = parser.parse(content)
        return extracted_data.dict()

# Function to regenerate article
def regenerate_article(extracted_data: Dict) -> Dict:
    title = extracted_data.get('title')
    newsUpdateType = extracted_data.get('newsUpdateType')
    recieverCategory = extracted_data.get('recieverCategory')
    recieverCountry = extracted_data.get('recieverCountry')
    date = extracted_data.get('date')
    projectFinanced = extracted_data.get('projectFinanced')
    project_name = projectFinanced.get('name', 'Unknown') if projectFinanced else 'Unknown'

    organizationFinanced = extracted_data.get('organizationFinanced')
    organization_name = organizationFinanced.get('name', 'Unknown') if organizationFinanced else 'Unknown'

    sub_updates = [sub['organization'] + ' (' + sub['role'] + ')' for sub in extracted_data.get('subUpdates', [])]

    regenerate_prompt = f"""
        Assume you are an expert in re-generating an article. Based on the following extracted data about a solar power plant, 
        generate an article consisting of 600 words:

            Title: {title}
            News Update Type: {newsUpdateType}
            Receiver Category: {recieverCategory}
            Receiver Country: {recieverCountry}
            Date: {date}
            Project Financed: {project_name}
            Organization Financed: {organization_name}

        Ensure the article is clear, informative, and fits within 600 words.
    """

    response = model(regenerate_prompt)
    
    if isinstance(response, AIMessage):  
        generated_content = response.content  
    else:
        generated_content = str(response)  

    return {
        "title": extracted_data.get('title', 'Untitled'),
        "content": generated_content
    }

# Data model for Database
class RequestDataForDB(BaseModel):
    title: str
    newsUpdateType: str
    receiverCategory: str
    textOfArticle: str
    receiverCountry: List[str]
    date: str
    totalAmount: float
    subUpdates: Optional[List[dict]] = None
    organizationFinanced: Optional[dict] = None
    projectStatus: Optional[str] = None
    projectStatusDate: Optional[str] = None
    technologyAndGridSystem: Optional[str] = None
    typeOfInstallation: Optional[str] = None
    gridType: Optional[str] = None
    pvSize: Optional[float] = None
    projectFinanced: Optional[str] = None

    @validator('projectFinanced', pre=True, always=True)  
    def extract_project_financed_name(cls, value: Optional[Dict[str, Any]]) -> Optional[str]:  
        if isinstance(value, dict) and 'name' in value:  
            return value['name']
        return value

# Pydantic model for request data
class RequestData(BaseModel):
    input: Union[str, None] = None  

status = False

# Endpoint to extract data for update
@app.post("/extract-data-update/")
def extract_data_update(request_data: RequestData):
    global status
    article = ""
    extracted_date = None
    extracted_text_of_article = ""  

    if request_data.input.startswith("http://") or request_data.input.startswith("https://"):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--headless")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(request_data.input)
            content = driver.find_element(By.TAG_NAME, "article")
            
            headers = '\n'.join([h_tag.text for h_tag in content.find_elements(By.XPATH, './/h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6')])
            para = '\n'.join([p_tag.text for p_tag in content.find_elements(By.TAG_NAME, "p")])
            extracted_text_of_article = headers + "\n" + para  

            if extracted_text_of_article:
                status = True  
            else:
                print("No article content extracted via Selenium")
        except Exception as e:
            print(f'Error occurred during Selenium extraction: {str(e)}')
    
    if not status and (request_data.input.startswith("http://") or request_data.input.startswith("https://")):
        try:
            print('\n\nEntering fallback mechanism!\n\n')
            response = requests.get(request_data.input)
            response.raise_for_status()
            article = response.text  
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Error fetching article from URL: {str(e)}")
    else:
        article = request_data.input  

    smart_scraper_graph = SmartScraperGraph(
        prompt="""
            Assume you are an expert in extracting data of solar power plants from articles.
            An article will be given as an input, and your task is to find and extract the following details from the article:

               - receiverCountry: Can list multiple countries, separated by commas, This is the country
                                          of the project or organization receiving the investment. Should only show the country! No
                                          region, continent
               - date: The date of the news update. Format should be "dd/mm/yyyy".
               - totalAmount: Total funding amount an integer or float value, this should be an full amount figure.
            """,
        source=request_data.input,  
        config=graph_config
    )
    
    try:
        result = smart_scraper_graph.run()
        extracted_country = result.get('receiverCountry', None)
        extracted_date = result.get('date', None)
        extracted_totalAmount = result.get('totalAmount', None)
        print(f'\n\nExtracted country: {extracted_country}, date: {extracted_date}, amount: {extracted_totalAmount}\n\n')

        if extracted_country and ',' in extracted_country:
            extracted_country_list = [country.strip() for country in extracted_country.split(',')]
        elif extracted_country:
            extracted_country_list = [extracted_country.strip()]
        else:
            extracted_country_list = "NA"
        
    except Exception as e:
        print('Error extracting data with SmartScraperGraph: ', str(e))
        extracted_country_list = "NA"

    extracted_data = generate_extracted_data(article)
    
    try:
        if extracted_country_list != "NA":
            extracted_data['receiverCountry'] = extracted_country_list 
        if extracted_date != "NA":
            extracted_data['date'] = extracted_date
        if extracted_totalAmount != "NA":
            extracted_data['totalAmount'] = extracted_totalAmount
    except Exception as e:
        print('Error applying SmartScraperGraph check: ', str(e))
    
    return extracted_data

# Endpoint to store data in Database
@app.post("/store-extracted-data/")
def store_extracted_data(request_data: RequestDataForDB):
    extracted_data = request_data.dict()

    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM updates WHERE title = %s)", 
                (extracted_data['title'],)
            )
            title_exists = cursor.fetchone()[0]

            if title_exists:
                return {"message": f"Data with title '{extracted_data['title']}' already exists in the database. Skipping insert."}

            if 'subUpdates' in extracted_data:
                insert_sub_updates(conn, extracted_data['subUpdates'])
            
            if extracted_data['receiverCategory'] == 'Project':
                insert_project_data(conn, extracted_data)
            elif extracted_data['receiverCategory'] == 'Organization':
                insert_organization_data(conn, extracted_data)
            
            insert_update_data(conn, extracted_data)

    except Exception as e:
        return {"error": str(e)}
    
    finally:
        conn.close()

    return {"message": "Data processed and stored successfully"}

# Endpoint to re-generate article
@app.post("/generate-article/")
def generate_summary(request_data: RequestData):
    global status 
    
    article = ""
    
    if request_data.input.startswith("http://") or request_data.input.startswith("https://"):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--headless")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(request_data.input)
            content = driver.find_element(By.TAG_NAME, "article")
            
            headers = '\n'.join([h_tag.text for h_tag in content.find_elements(By.XPATH, './/h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6')])
            para = '\n'.join([p_tag.text for p_tag in content.find_elements(By.TAG_NAME, "p")])
            article = headers + "\n" + para
            
            # print(article)
            if article:
                status = True 
                # print(f'\n\nFlag Status: {status}\n\nArticle Text: {article}')
            else:
                print("No article content extracted")
        except Exception as e:
            print(f'Error occurred during processing article: {str(e)}')
    
    if not status and (request_data.input.startswith("http://") or request_data.input.startswith("https://")):
        try:
            print('\n\nEntering fallback mechanism!\n\n')
            response = requests.get(request_data.input)
            response.raise_for_status()
            article = response.text
            # print(article)
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Error fetching article from URL: {str(e)}")
    else:
        article = request_data.input

    extracted_data = generate_extracted_data(article)
    regenerated_article = regenerate_article(extracted_data)
    regenerated_article = {
        "title": regenerated_article.get("title"),
        "content": regenerated_article["content"]
    }
    return regenerated_article

# Endpoint to extract original text of article
@app.post("/extract-original-text/")
def extract_original_text(request_data: RequestData):
    article = ""
    status = False 

    if request_data.input.startswith("http://") or request_data.input.startswith("https://"):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--headless")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(request_data.input)
            content = driver.find_element(By.TAG_NAME, "article")

            headers = '\n'.join([h_tag.text for h_tag in content.find_elements(By.XPATH, './/h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6')])
            para = '\n'.join([p_tag.text for p_tag in content.find_elements(By.TAG_NAME, "p")])
            article = headers + "\n" + para
            driver.quit()

            if article:
                status = True
                return {"originalText": article, "source": "original"}
            else:
                print("No article content extracted using Selenium.")
        except Exception as e:
            print(f'Error occurred during processing article: {str(e)}')


    if not status and (request_data.input.startswith("http://") or request_data.input.startswith("https://")):
        try:
            print('\n\nEntering fallback mechanism!\n\n')
            response = requests.get(request_data.input)
            response.raise_for_status()
            article = response.text 
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Error fetching article from URL: {str(e)}")
    else:
        article = request_data.input

    extracted_data = generate_extracted_data(article)
    extracted_data['textOfArticle'] = extracted_data.get('textOfArticle', article)
    original_text = extracted_data['textOfArticle']
    return {"originalText": original_text, "source": "openai"}

