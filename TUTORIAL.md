# Beginner tutorial — set up Shoovy Farmer on your PC

This guide assumes you have never done anything like this before. Follow it in order. It takes
about 20 minutes the first time. Everything runs on your own Windows PC.

At the end you will have: your worker accounts auto-fishing and sending their credits to your
main account 24/7, and a web page to watch it all.

---

## Step 1 — Install Go (once)

Go is the free tool that turns the code into runnable programs.

1. Open https://go.dev/dl/ in your browser.
2. Download the Windows installer (the `.msi` file).
3. Run it, click Next until it finishes.
4. To check it worked: press `Windows key`, type `cmd`, open **Command Prompt**, type `go version`
   and press Enter. You should see something like `go version go1.24 windows/amd64`. If you do,
   Go is installed.

## Step 2 — Download this project

1. On the project page on GitHub, click the green **Code** button, then **Download ZIP**.
2. Right-click the downloaded ZIP, choose **Extract All**, and pick a simple folder like
   `C:\shoovy-farmer`. Avoid spaces and OneDrive folders if you can.
3. Open that folder. You should see `build.bat`, `install-startup.bat`, and several folders.

## Step 3 — Build the bots

Double-click **`build.bat`**. A black window opens, shows "building ..." for each bot, then
"Done." A new `bin\` folder appears with the programs inside. If it says BUILD FAILED, make sure
Step 1 worked (`go version` in a Command Prompt).

## Step 4 — Get your accounts' cookies (the important part)

The bots log in as you by reusing your browser's login cookies. You need, **for each account**,
two things from two websites. The easiest way is a free browser extension.

1. Install the **Cookie-Editor** extension (search "Cookie-Editor" in the Chrome or Firefox
   add-on store, add it).
2. For the account you want to use as a **worker**:
   - Go to **kick.com** and log into that account.
   - Click the Cookie-Editor icon while on kick.com, click **Export** (choose "Export as JSON").
     This copies all the kick.com cookies. Keep them, you will paste them soon.
   - Inside those cookies, find the one named **`session_token`** — its value is also your
     "bearer".
   - Now go to **shoovy.wtf** and make sure you are logged in there too (click "Log in with Kick").
   - Open Cookie-Editor again while on shoovy.wtf, find the cookie named **`session`**, and copy
     its value. That is your `shoovy_session`.
3. Repeat for each worker account.
4. For your **main account** (the one that should collect everything): you only need its
   **shoovy.wtf `session`** cookie (so the dashboard can show its balance). No bot acts on it.

> Tip: cookies expire after a while (about a month). If a bot later says "session invalid", just
> redo this step to get fresh cookies.

## Step 5 — Fill in accounts.json

1. In the project folder, make a copy of `accounts.example.json` and name the copy
   **`accounts.json`**.
2. Open `accounts.json` in Notepad. Replace the placeholders:
   - `name`: any label you choose. **Use the account's real Kick username for your main account**
     (the tip command needs it).
   - `bearer`: the value of the `session_token` cookie (workers only).
   - `cookies`: paste the JSON array you exported from kick.com (workers only).
   - `shoovy_session`: the `session` cookie value from shoovy.wtf.
3. Keep the main account first, then your workers. Save the file.

## Step 6 — Point the config at your accounts

Open these small files in Notepad and change only the names to match your `accounts.json`:

- **`fisher.config.json`** → `"workers"`: list your worker account names, e.g.
  `["Worker1", "Worker2"]`.
- **`econ.config.json`** → `"workers"`: same worker names. `"target_user"`: your **main account's
  Kick username** (this is who receives the tips).
- **`dashboard.config.json`** → `"target"`: your main account name (as written in accounts.json).

Everything else (the channel, the cooldowns, the anti-spam limits) is already set correctly for
shoovy. You do not need to touch it.

## Step 7 — Turn it on 24/7

Double-click **`install-startup.bat`**. It registers the farmer to start automatically every time
you log into Windows, and starts it right now in the background. That is your 24/7.

> A home PC that stays on and logged in will run it around the clock. If you log out or shut down,
> it resumes when you log back in.

## Step 8 — Watch it

Open your browser at **http://127.0.0.1:8088**. You will see:

- your **main account net worth** (the number you want to grow),
- each account's balance,
- the live market prices,
- which bots are up,
- when each worker will next tip,
- and a red **STOP** button.

Give it a few minutes. `fisher` waits for the fishing cooldown before its first cast (this is
normal and on purpose, to avoid spam). Check `data\fisher.log` and `data\econ.log` to see activity.

---

## Everyday use

- **Stop everything now:** click **STOP** on the dashboard, or double-click `stop.bat`.
- **Resume:** click **Start** on the dashboard, or double-click `start.bat`.
- **Remove auto-start:** `uninstall-startup.bat`.
- **Test in the foreground** (see a console with live output): `run.bat` (close the window to stop).

## Troubleshooting

- **A bot shows "session invalid" / red on the dashboard:** the cookies expired or were pasted
  wrong. Redo Step 4 and Step 5 for that account.
- **fisher logs `BANNED` or errors:** the account was rate-limited or the fishing feature is off.
  fisher backs off automatically (waits 45 minutes) and the watchdog protects you. Just leave it.
- **Nothing happens for a while:** that is expected. Fishing has a 15 minute cooldown, and tips
  only go out once every 36 hours. It is designed to be slow and quiet on purpose.
- **The dashboard page does not open:** make sure the bots are running (`run.bat` shows output),
  and that you typed `http://127.0.0.1:8088` exactly.

## What it will and will not do

It **will**: fish, claim daily, and funnel worker credits to your main account, quietly, 24/7.

It **will not**: touch your main account, trade the stock market, or do anything fast/spammy. Those
are deliberate choices to keep your accounts safe.
