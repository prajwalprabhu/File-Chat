create .env file

get a API key from https://console.groq.com/playground
This would be the typical .env file

````
GROQ_API_KEY = Your API Key
SECRET_KEY= This is a secrete for the cookies,
UPLOAD_FOLDER = "uploads"
EMBEDDINGS_DIR = "embeddings"
EMBEDDINGS_MODEL = "all-mpnet-base-v2" ```
````

install the requirements

```
pip install -r requirements.txt
```

run the app

```
fastapi run app.py
```

Then open the link provided by the server.
