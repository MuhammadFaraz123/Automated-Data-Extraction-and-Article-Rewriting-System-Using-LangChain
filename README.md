
# Automated Data Extraction and Article Rewriting System Using LangChain

This project is a FastAPI-based system that automates data extraction from articles, rewrites the content, and stores the extracted data into a PostgreSQL database. It uses LangChain and the OpenAI API to process and analyze article data, specifically related to updates and rewriting articles.

## Features

- **Data Extraction**: Extract specific fields of data from articles.
- **Article Rewriting**: Automatically generate a rewritten version of the article.
- **Original Text Extraction**: Extract the original text from an article.
- **Data Storage**: Store extracted data into a PostgreSQL database.

## Targeted Industry

- **Solar Power Plants**: Here the targeted domain is solar power plants. You can target any specific domain or industry by modifying prompt and Data models according to your usecase. 

## Prerequisites

Before you start, make sure you have:

- Python 3.8+
- PostgreSQL database installed
- Access to the OpenAI API

## Installation

### Step 1: Install PostgreSQL

To install PostgreSQL, follow these steps:

1. Update your package lists:
   ```bash
   sudo apt update
   ```
2. Install PostgreSQL:
   \`\`\`bash
   sudo apt install postgresql postgresql-contrib
   \`\`\`

### Step 2: Access PostgreSQL

To access the PostgreSQL database, use the following command:
\`\`\`bash
sudo -i -u postgres
\`\`\`

Once inside the PostgreSQL shell, you can create a new database and user.

### Step 3: Create a New Database

\`\`\`bash
createdb article_data
\`\`\`

### Step 4: Set Environment Variables

Update your \`.env\` file to include your PostgreSQL credentials. Add the following environment variables to the file:

\`\`\`bash
DB_NAME=db_name
DB_USER=db_username
DB_PASSWORD=db_password
DB_HOST=host_ip
DB_PORT=port
OPENAI_API_KEY=your_openai_api_key
\`\`\`

## API Endpoints

You can interact with the system using the following API endpoints via \`curl\`.

### 1. Extract Data of Updates

This endpoint extracts updates from an article and analyzes specific fields.

\`\`\`bash
curl -X POST http://<ip>:<port>/extract-data-update/ \
     -H "Content-Type: application/json" \
     -d '{"input": "<url_or_text>"}'
\`\`\`

### 2. Re-Generate Article

This endpoint regenerates the article content based on extracted data.

\`\`\`bash
curl -X POST http://<ip>:<port>/generate-article/ \
     -H "Content-Type: application/json" \
     -d '{"input": "<url_or_text>"}'
\`\`\`

### 3. Extract Original Article Text

This endpoint extracts the original text from an article for further processing.

\`\`\`bash
curl -X POST http://<ip>:<port>/extract-original-text/ \
     -H "Content-Type: application/json" \
     -d '{"input": "<url_or_text>"}'
\`\`\`

### 4. Store Extracted Data into Database

This endpoint stores the extracted article data into the PostgreSQL database.

\`\`\`bash
curl -X POST http://<ip>:<port>/store-extracted-data/ \
     -H "Content-Type: application/json" \
     -d '{
    		"title": "<str>",
    		"newsUpdateType": "<str>",
    		"receiverCategory": "<str>",
    		"textOfArticle": "<str>",
    		"receiverCountry": [
        		"<str>"
    		],
    		"date": "<str>",
    		"projectFinanced": {
        		"id": "",
        		"name": "<str>"
    		},
    		"projectStatus": "<str-or-null>",
    		"projectStatusDate": "<str-or-null>",
    		"technologyAndGridSystem": "<str-or-null>",
    		"typeOfInstallation": "<str-or-null>",
    		"gridType": "<str-or-null>",
    		"pvSize": <int-or-float-or-null>,
    		"organizationFinanced": <str-or-null>,
    		"totalAmount": <int-or-float>,
    		"subUpdates": [
        		{
            		"organization": "<str>",
            		"role": "<str>",
            		"instrument": "<str>",
            		"amount": <int-or-float>,
            		"financingStructure": "<str>"
        		},
        		...
    		]
	}'
\`\`\`

## Running the Project

Once the environment is set up and the database is configured, you can run the FastAPI server with:

\`\`\`bash
uvicorn main:app --reload --host <host-ip> --port <port>
\`\`\`

## Contributing

Feel free to open issues or create pull requests for any improvements or bugs.

