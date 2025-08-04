Toki the Discord Bot

how to build Project Environment:


1.  Build Virtual Environment
```bash
python -m venv venv
```

2.  ActivateVirtual Environment
```bash
.\venv\Scripts\activate
```

3.  Install Packages
```bash
pip install -r requirements.txt
```

4.  Install New Packages (ex: discord)
```bash
pip install discord
```

5.  Update requirements.txt
```bash
pip freeze > requirements.txt
```

6.  Build .env File
```bash
DISCORD_TOKEN=your_token_here
```

Warning:
Please install all packages in the virtual environment (execute activate first)

After installing a new module, please use ```bash pip freeze > requirements.txt```  IMMEDIATELY (YOU BETTER DO IT) 

DO NOT UPLOAD .env files to GitHub to protect information


Dolist:

1. Reaction on user's message module (with custom emoji)
2. Post game news on specific channel
3. Alert every month's 15th use Mr.crab meme (Funny)
4. Every Friday post "Today is Friday in California"(Funny)
5. Use AI detect Picture command specific 
6. Learn more AI stuff i guess