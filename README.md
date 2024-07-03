DEPENDENCIES TO INSTALL:

```
pip3 install python3
pip3 install requests
pip3 install PyYaml
pip3 install http
pip3 install asyncio
pip3 install aiohttp
```

HOW TO RUN:

Run these commands in terminal in this directory:

```
python3 dota2infopull.py "top N teams" output.yaml
python -m http.server 8000
```

Then type http://localhost:8000/index.html in any web browser to view as a website

Once this localhost is set up, create a new terminal and run the file as many times as you want with its arguments

Wait a few seconds and refresh the page after each save into the yaml file

: Obtaining new cache data may take a few seconds due to 60 call per minute limit
