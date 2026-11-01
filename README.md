# J*b Finder

A local Streamlit website for finding jobs and internships. It searches LinkedIn first and any official company career sites you add. The Apply page has been removed. A result's **Use this site** link opens the direct application URL in a new tab when the job listing exposes one. Otherwise, **Open job listing** takes you to the listing so you can select Apply there.

## Run in VS Code

Open a terminal in this folder and run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your [TinyFish API key](https://agent.tinyfish.ai/api-keys) to `.env`, then start the app:

```powershell
python -m streamlit run app.py
```

If `.env` already exists, keep it and skip the copy command. If `python` is not recognized, use the full path to `python.exe` followed by `-m`. Run Streamlit from the terminal rather than VS Code's **Run Python File** button.

## How it works

1. In **Profile**, save your desired role, Job or Internship, annual salary range, earliest start date, and optional location and work mode. Your contact details and résumé are optional. They remain on your computer and are not sent to job sites by opening a result.
2. In **Find jobs**, select **Search job listings**. TinyFish Search and Fetch look for LinkedIn listings and links on your approved company career domains. The app filters out social media, video sites, and job aggregators.
3. Select **Use this site** when a clear application link is found. Streamlit opens that URL in a new tab. If the listing does not expose a direct application link, select **Open job listing** and use the site's Apply control. Some sites require sign-in or open the form in a popup, so a direct link may not exist.
4. The **Past results** tab shows records from earlier versions. Opening a link does not count or record a new application.

The app does not fill, upload, or submit a job application. Check the job and site before entering your details. Your `.env`, local profile, past results, and saved résumé are excluded from the ZIP and Git.

This uses the [TinyFish Search API](https://docs.tinyfish.ai/search-api/reference), [TinyFish Fetch API](https://docs.tinyfish.ai/fetch-api/reference), and [Streamlit link buttons](https://docs.streamlit.io/develop/api-reference/widgets/st.link_button).
