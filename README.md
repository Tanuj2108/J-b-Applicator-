# J*b Applicator

A local Streamlit website for finding job links with TinyFish and opening applications in a TinyFish Browser API session that attaches your saved résumé. It saves your profile, approved answers, and application results on **your computer**. It is intended for one user, not a shared public deployment.

## Start in VS Code

Use Python 3.11 or newer. Open a terminal in the `job_applicator` folder and run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and enter your [TinyFish API key](https://agent.tinyfish.ai/api-keys). Then start the site:

```powershell
python -m streamlit run app.py
```

If `python` is not recognized, use the full path to your `python.exe` followed by `-m`. Use the VS Code terminal; **Run Python File** does not start Streamlit correctly.

If installing Playwright into Python reports an access-denied error, install just the browser support inside this app folder instead. No local Chrome or Edge installation is needed for résumé attachment:

```powershell
python -m pip install --target .deps "playwright>=1.55,<2"
```

## Workflow

1. **Profile:** enter your first and last name, contact and address details, education, résumé text, desired role, Job or Internship, annual minimum and maximum salary, currency, earliest available start date, and work mode. Red `*` marks fields needed to save the profile; education fields are required for internships. Click **Save résumé file and extract text** after choosing a PDF or TXT file. The original file is stored locally in `.private/`; it is not uploaded to a job site by the TinyFish Agent run.
2. **Find jobs:** TinyFish Search finds LinkedIn job pages, then TinyFish Fetch reads individual job links from them. You may also list official company career URLs; searches and results are restricted to those domains. Instagram, YouTube, TikTok, other social sites, and job aggregators are excluded. Open and verify each listing, then select one or queue several for individual review. A salary shown as **In range** was recognized from a listing; **Salary not verified** means you must check it. Earliest start date is saved as your availability and must be checked against the job description. The page shows whether TinyFish returned results or an error.
3. **Attach résumé in TinyFish browser:** in Apply, click **Open TinyFish browser and attach résumé**. Click **Refresh browser status** until **Open TinyFish browser** appears, then open that link. Sign in there if required and navigate to the application form. The helper selects your original PDF or TXT in an unambiguous résumé upload control. Refresh the status again, then check that the job site shows the correct attachment. Complete other fields and submit the application yourself in that browser. If the site has several ambiguous file inputs or rejects the file type, select the correct control yourself. Click **Close TinyFish browser** when finished to stop the session. The app also closes it after 30 minutes.
4. **Optional TinyFish inspection:** TinyFish can separately fill text fields for inspection. It uses its own Agent browser; your Browser API attachment is not in that run. If that separate run needs sign-in, you can use a [TinyFish Browser Context Profile](https://docs.tinyfish.ai/key-concepts/browser-context-profiles) and [TinyFish Vault](https://docs.tinyfish.ai/key-concepts/credentials). It never clicks the final Submit button. Direct Browser API sessions do not reuse that profile or Vault; sign in yourself through the TinyFish browser link.
5. If the form asks a question the app cannot answer, enter and save the answer, then retry. Login, résumé file upload, CAPTCHA, and vague manual-completion notices from the optional TinyFish run appear as **manual steps**, never as answer boxes. Do not type passwords into saved answers.
6. Previous TinyFish results remain in Results. New submissions you make in the TinyFish browser are not automatically counted in that history; keep the job site's confirmation or email.

The **Submit after filling** control for the separate TinyFish Agent run remains disabled. The Browser API helper does not click Submit or agree to legal terms on your behalf. A selected file in the browser is not proof the job site accepted the upload; check the site's filename or upload confirmation before you submit.

## Limits and privacy

- The app never asks for or saves website passwords. `.env` holds only your TinyFish API key and is excluded from version control.
- The original résumé file is stored locally in `.private/` and sent to the selected job site's file control through the TinyFish Browser API session. It is removed locally when you delete the saved profile. Résumé text, profile fields, approved answers, and result summaries are local JSON files. Do not put passwords or identity documents in them. Keep the folder private, especially if it syncs with OneDrive.
- TinyFish receives the details used in an agent run. Deleting a Browser Context Profile clears its saved login state, but does not prove that run history or site-submitted data was erased.
- Job sites can require file uploads, CAPTCHA, MFA, legal declarations, or unusual questions. The browser helper attaches only when it identifies a suitable file control; the separate TinyFish Agent run cannot attach the stored file and never submits a new application.
- TinyFish Browser API sessions are billed while running. Close the session from the Apply page when finished. Search and Agent usage follow your TinyFish account terms.

Implementation follows the [TinyFish Search API](https://docs.tinyfish.ai/search-api/reference), [Browser API](https://docs.tinyfish.ai/browser-api/reference), and [Playwright file upload API](https://playwright.dev/python/docs/input).
