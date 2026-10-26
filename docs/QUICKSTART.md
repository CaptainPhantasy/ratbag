# RATBAG QuickStart
## Or: Your first useful run, before the coffee goes cold.

**DOCUMENT CLASSIFICATION:** First-run guide / No secret handshake

**DATE RECORDED:** October 19, 2026

**LOCATION:** Floyd Labs, at the useful end of the workbench

**BEVERAGE:** Coffee that tastes like motor oil. Bring your own if you prefer.

**CURRENT STATE:** One small task away from knowing the controls

Your first run should teach you the whole loop: choose a project, describe a change, watch the checks, and download the result. The practice project is real code created for that purpose. It does not change your own project.

Have your GLM, DeepSeek, and MiniMax account keys ready if the server operator has not already supplied them. If those accounts already show keys, keep the saved setup. You do not need an optional Optional router key for this walkthrough.

## 1. Open the workbench (Or: Start here)

After the operator completes the [installation](../README.md#install), open [RATBAG on the server](http://127.0.0.1:8765/) from a device that can reach private network. If the app asks for a **Server access** key, enter the key for this RATBAG installation. This is different from your model account keys.

Select **Help → Run guided setup**. A new browser may offer the same walkthrough from the setup card. On the iPhone layout, **More** provides the application controls.

**You should see:** the setup steps **Welcome**, **Project**, **Accounts**, **Routing**, and **Ready**. You can go back and correct a selection before creating a task.

If the address does not open, first check whether [the server itself](http://127.0.0.1/) opens. The [manual's connection recovery section](USER_MANUAL.md#connection-recovery) gives the next action for each result.

## 2. Choose a practice project (Or: Learn on something disposable in spirit, retained in fact)

At **Project**, select **Create practice project**. Wait for **label-workshop** to appear, then select it. RATBAG creates a small working example on the server. This step does not call a model. If that practice project already exists, the button reopens it without overwriting its files.

For a real project instead, choose it from the **Project** menu. The menu lists projects already on the server. A folder on your iPhone or a link to GitHub is not the same thing as a server project. If your project is missing, use the manual's [project instructions](USER_MANUAL.md#projects).

**You should see:** the selected project and available checks. The practice project includes its own checks so you can learn the workflow without installing project dependencies.

## 3. Connect the accounts (Or: Your keys, your crew)

At **Accounts**, enter only the keys the app says are missing:

| Account field | What it supplies |
| --- | --- |
| GLM | Architect and Tests & review |
| DeepSeek | Builder |
| MiniMax | Find files and Find references |
| Optional Optional router | An optional model used for an ambiguous routing decision; leave disabled for this first run |

Select **Check connections**. In guided setup, that button saves the entered keys first and then checks the four core roles. **Continue** also saves entered keys if you choose to move on without a live check. In **Models → Accounts**, the separate **Save accounts** button saves without checking.

**You should see:** an individual result for Architect, Builder, Scout, and Auditor. A saved key and a successful connection are separate states. Read the result for any role that does not pass before starting a task.

If a key is rejected, correct that account entry and check it again. If the optional Router connection fails, disable it in **Models → Advanced** and continue with the four core roles. You do not need to paste the same GLM key twice in guided setup.

Keys entered here stay in server memory. The fields can appear blank again after saving; that keeps the saved secret out of the page. The key-present status tells you whether an entry remains available. A server restart clears keys that were entered in the app unless the operator separately supplies them through the server environment.

## 4. Keep Smart routing (Or: Start with the known arrangement)

At **Routing**, choose **Smart**. This applies the intended model for each role and explains the arrangement. Choosing the preset does not send a model request.

Smart uses GLM for architecture and audit, DeepSeek for building, and MiniMax for both scouts. It is an explicit starting arrangement. It does not guess a price, rank your accounts, or silently switch to another provider after an error.

At **Ready**, select **Create first task**. This opens a task form; it does not start paid model work yet.

## 5. Describe one result (Or: Give the team something it can finish)

In **New task**:

1. Confirm the practice project in **Project**.
2. Choose an appropriate **Starting point**, or keep a blank request.
3. Use the practice project's suggested task in **Task**, or paste the request below.
4. Keep the recommended entry in **Checks**.
5. Keep **Smart** in **Model routing**.
6. Leave **Advanced options** at their defaults.
7. Select **Start task**.

Use this request for **label-workshop**:

> Update normalize_label to trim surrounding whitespace and collapse every run of whitespace, including tabs and newlines, to one ASCII space. Preserve letter case. Return an empty string for whitespace-only input and keep raising TypeError for non-string input. Add focused tests.

Its check command is **python3 -m unittest discover -s tests -v**. The prepared example starts with three tests; the requested change asks the Builder to add focused coverage. A clear expected result helps the Builder and reviewers agree on what to check. “Improve everything” gives them much less to work with.

**You should see:** a saved task and an actual stage, followed by activity as work proceeds. **Start task** uses your configured providers and can use account credits. Repeated clicks are not needed.

## 6. Follow the work (Or: Watch the work, not a pretend percentage)

The app finds relevant files, prepares a plan, gets the Architect's review, builds a candidate, runs checks, and requests final review. It may repair an unsuccessful attempt within the limits you chose.

Open **View evidence**, **View findings**, **View checks**, or an activity event to see what supports the current result. A review that rejects the work prevents it from being marked ready.

| Control | What happens |
| --- | --- |
| Pause | Requests a pause after the current operation reaches a safe stopping point. Wait until the app says Paused. |
| Resume | Continues saved work after a pause or interruption. |
| Stop | Requests the end of this run. Saved work remains. An in-flight provider request can take time to end. |
| Revise task | Opens a new task with the prior settings prefilled so you can correct the request or checks. |

On iPhone, use **Work**, **Team**, and **Activity** to move between focused views. On larger layouts, more of those views appear together.

If the app says **Needs input**, read the next-action message. Repair an account or connection problem, then resume when offered. If the task, selected checks, or limits need changing, select **Revise task** instead, correct the prefilled details, and select **Start new run**. The [manual's recovery table](USER_MANUAL.md#recovery) covers the common messages.

## 7. Inspect and save the result (Or: Bella insists on seeing the work)

When the run says **Ready for review**:

1. Open **View checks** and read the actual check result.
2. Open **Final review** to see the Architect's decision.
3. Open **View evidence** to inspect the proposed changes.
4. Select **Download patch**. On a phone or iPad, use the browser's download or share controls to keep the file in Files.

The patch is a saved description of the changes. Downloading it does not change the original project, create a commit, or publish anything. RATBAG keeps the tested candidate and evidence on the server. A project maintainer can review and apply that result through the project's normal process.

**Your first run is complete when:** you can reopen it from **History**, read the check and review evidence, and download the preserved patch. If the run needs correction, its evidence is still available and **Revise task** gives you the next attempt with the starting details already filled in.

## 8. Set the screen to suit you (Or: The dark side is optional)

Open **View** and choose **System**, **Dark**, **Light**, or **High contrast**. Choose **Automatic** for the layout, or explicitly choose **iPhone**, **iPad**, **Desktop**, **Widescreen**, or **Ultrawide**.

The mascot's waist pack stays safety orange. Its background, surrounding lettering, and contrast follow the selected theme.

These are display choices. They do not alter a task, change the models, or use provider credits. The [full manual](USER_MANUAL.md#appearance) explains what each layout brings forward.

**DOCUMENT ENDS**

*Floyd Labs — First Run Department*

*The coffee can be questionable. The next step should not be.*

| Garage notes | Status |
| --- | --- |
| Bella | Reviewing your choice of desk space |
| Bowser | Waiting for the check result |
| Boardroom detour | Skipped |
