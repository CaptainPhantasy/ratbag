# RATBAG User Manual
## Or: Every control explained. No boardroom translation required.

**DOCUMENT CLASSIFICATION:** Owner's manual / Built for the person doing the work

**DATE RECORDED:** October 19, 2026

**LOCATION:** Floyd Labs, the garage with the suspicious coffee

**BEVERAGE:** Coffee that tastes like motor oil; refill optional

**CURRENT STATE:** Giving you the controls and the reasons behind them

RATBAG takes a coding request, works on a separate copy of the selected project, and keeps the proposed changes with the checks and reviews that support them. You can follow it, pause it, stop it, return later, and download the result.

If this is your first visit, follow the [QuickStart](QUICKSTART.md). Use this manual when you want to know exactly what a control does or how to recover from a problem. In the browser help, search by the thing you want to do: **project**, **key**, **pause**, **download**, or **theme**.

<a id="open"></a>
## Open and connect (Or: Get through the front door)

After the operator completes the [installation](../README.md#install), open [RATBAG on the server](http://127.0.0.1:8765/) while your device can reach private network. The installed app runs on the server. Your browser sends instructions and displays results; it does not need Python or Git installed on the phone or iPad.

If **Server access** appears, enter the access key for this RATBAG installation and select **Connect**. That key is separate from GLM, DeepSeek, MiniMax, and OpenRouter account keys. If you do not have the server access key, the person maintaining the server supplies it.

The server access key stays in the open page's memory. Reloading or closing that page clears it. It is never part of the URL. The app's connection indicator shows whether the page can reach the server. If the connection drops, select **Reconnect** after the network is available again.

Closing the browser does not issue **Stop**. The server can continue the task. Reopen the app and use **History** to return to the saved run. If the server itself stopped, an unfinished run may show **Interrupted** and offer **Resume** after the service returns.

<a id="navigation"></a>
## Find your way around (Or: The places worth knowing)

| Place | Use it for |
| --- | --- |
| Workspace | The current task, its stage, team activity, review checkpoints, controls, and outcome. |
| Projects | Choose a project already on the server or create the practice project. |
| History | Reopen a saved task and its evidence. |
| Models | Account keys, connection checks, Smart or Manual routing, and advanced model settings. |
| View | Theme and workspace layout choices. |
| Help | Guided setup, QuickStart, and the full manual. |

**New task** starts a new request. On the iPhone profile, bottom navigation divides the workspace into **Work**, **Team**, **Activity**, and **More**. More exposes the application controls without squeezing them into a tiny toolbar.

Open an item to inspect its details. Disabled evidence or review buttons mean there is no saved result for that item yet. A muted “Not running” state is not a failure. It can mean that the role is waiting for the stage when it is needed.

<a id="onboarding"></a>
## Guided setup (Or: Nobody should need a secret handshake)

Open **Help → Run guided setup** whenever you need a refresher. The walkthrough has five steps:

| Step | What to do | What it changes |
| --- | --- | --- |
| Welcome | Read the short introduction and continue. | Nothing runs yet. |
| Project | Select an existing project or choose **Create practice project**. | Selects a server project; creating the practice project writes a small example project on the server. |
| Accounts | Enter the required keys and select **Check connections**. | The walkthrough saves entered keys first, then checks the four core roles. Continue can save without checking. |
| Routing | Keep **Smart**, or choose **Manual** if you have already configured your own roles. | Selects the model arrangement; choosing it does not call a model. |
| Ready | Review readiness and select **Create first task**. | Opens the task form. The task starts only when you select **Start task**. |

Use **Back** to correct an earlier choice. A key-present label means the server has an entry; a connection-check result means a real request returned a result. The walkthrough does not turn one into the other.

Use **Explore workspace** if you want to look around first. You can leave guided setup and reopen it later. It does not erase projects, account settings, or saved runs. Select **Get started** on Welcome and **Continue** through the intermediate steps; the final action is **Create first task**.

<a id="projects"></a>
## Projects (Or: Pick the workbench, not a mystery path)

Open **Projects**, or use the **Project** menu in **New task**. RATBAG lists Git projects found in the server folders configured by the operator. A Git project is a project folder whose change history is managed by Git.

Use **Find a project** to filter the list by name or folder, then choose a project by its displayed name and confirm the server path shown with it. That path identifies the actual folder the task will use. Two projects can have similar names; the path keeps them distinguishable.

### Use the practice project

Select **Create practice project**. The app creates **label-workshop**, a real small project with three starting checks and a suggested change to `normalize_label`. Choose it for a first run or to confirm that the app can complete the workflow. Creating it does not use a model. Running a task against it does. Selecting the button again reopens the existing practice project without overwriting its files.

### If a project is missing

Select **Refresh projects** after the project has been placed on the server. If it still does not appear, open **My project is not listed → Use a folder path** and enter its full server path in the new task’s **Project folder** field. Select **Inspect folder** to read its available checks before running. You can also choose **Advanced — enter a server folder** in the task’s Project menu. The the server operator can include the parent folder in `SWARM_PROJECT_ROOTS` to make it appear in the picker.

The picker does not upload a project from your device or clone a GitHub URL. If the code exists only on another machine or on GitHub, have the project maintainer place a working copy on the server and prepare its test tools. Do not enter a website address into a filesystem-path field.

### What the task does to your project

RATBAG captures a fixed starting copy and includes safe local changes it can read. It builds and checks candidates separately. The original project files stay unchanged by the run. Subsequent edits to your original project do not silently change the already captured starting copy.

If you want a run to include newer project edits, create a new task. Resume continues its saved starting point.

<a id="accounts"></a>
## Accounts and connection checks (Or: Your keys, your crew)

Open **Models → Accounts**. The normal setup asks for provider accounts instead of making you configure each role from scratch.

| Account | Used by | Needed for Smart mode |
| --- | --- | --- |
| GLM | Architect and Tests & review | Yes; one guided account entry supplies both roles. |
| DeepSeek | Builder | Yes |
| MiniMax | Both scouts | Yes |
| Optional router | Optional model assistance for ambiguous routing | No |

Enter a key only in its account key field, then select **Save accounts**. Do not put keys in a task description, project file, model name, or provider address. A key field can be blank after saving because the page does not show the secret again. Look at the key-present status to confirm that the server has an entry.

In Models, **Save accounts** saves without sending a model request. **Check connections** saves any entries first, then sends a small request to each core role and reports each result. A successful GLM Architect check does not stand in for the GLM Auditor check; both actual model selections are checked.

### Understand the results

| Result | Meaning | Next step |
| --- | --- | --- |
| Key needed | This role has no available session or server-environment key. | Add the corresponding account key and save. |
| Key saved · not checked | The entry is available, but no successful check is recorded for the current settings. | Select **Check connections**, or check that role in Advanced. |
| Connection checked | The selected model returned an acceptable response at the recorded check time. | Continue setup or start the task. |
| Check failed | That request did not finish successfully. | Read the message, fix that account or setting, then check again. |
| Role disabled | That role is off. | Enable the core role before starting; optional Router can stay off. |

A check can use account credits. It is a connection test, not a benchmark or a promise that a coding task will succeed. The app does not repeatedly test on page load.

### Keys after closing or restarting

Keys typed in the app live in server memory. Closing a browser does not erase a key already saved to the server, but restarting the server does. If the operator supplies the model keys through the service environment, the service can read those values again when it starts.

Non-secret model settings and run history are saved separately. The browser remembers appearance choices, not provider secrets. See [the installation section in README](../README.md#install-it-yourself-or-for-the-person-maintaining-the server) for operator settings.

### Optional Optional router

The ordinary routing layer does not require OpenRouter. Open **Models → Advanced** for the optional Router connection’s enabled setting and its individual connection check. Saving an optional account key alone does not enable it. Leave the optional connection disabled when its key is missing, expired, or not wanted. With it disabled, an ambiguous check-command decision can use the native GLM auditor as the configured fallback.

This choice is explicit. A failure from an enabled provider does not cause a silent change to another account.

<a id="routing"></a>
## Smart and Manual routing (Or: Pick the arrangement, see the reason)

Open **Models → Routing**, choose a **Routing mode**, and select **Save routing**. You can also choose **Model routing** for a particular run in **New task**.

**Smart** applies the intended four-model preset:

| Role | Model | Why this role gets that setting |
| --- | --- | --- |
| Architect | GLM-5.3, maximum reasoning | Plan review, repeated-failure review, and final review. |
| Builder | DeepSeek Flash, high reasoning | Main planning, proposed changes, and repairs. |
| Both scouts | MiniMax M3.1 Flash, low reasoning | Bounded file and reference searches. |
| Tests & review | GLM-5.3-Flash, high reasoning | Review of the recorded checks and proposed changes. |

Smart restores this arrangement. Saving a core role in **Models → Advanced** automatically selects **Manual**, so the next task keeps your custom model and limits. Manual retains your saved model choices; it does not make you perform the coding steps yourself. You can explicitly choose Smart again to restore its preset.

The preset reports the selected arrangement and whether its required account entries are available. It does not calculate a quality score, invent a confidence percentage, find the cheapest provider, or silently switch a failed request elsewhere. Choosing a preset does not call a model.

### How the check command is chosen

The project inspector first looks for checks declared by the project. In **Checks**, a recommended choice has a reason grounded in those files. You may select another discovered check or choose **Advanced — use my own check command** to enter one explicit command.

If automatic discovery leaves an ambiguous choice, the routing layer may ask its configured model for a supported command. The resulting decision is recorded. A suggestion still has to pass the command rules; it cannot bypass them by sounding confident.

During a run, open **Routing** to inspect the selected command, source or reason, and measured elapsed time. That is evidence about this decision, not a universal latency guarantee.

<a id="new-task"></a>
## New task (Or: Give it a finish line)

Select **New task**. Each run is a saved request with its own starting copy, recorded model arrangement, checks, and limits.

| Field | What to choose | Example or useful default |
| --- | --- | --- |
| Project | The actual project on the server. | Practice project for a first run. |
| Starting point | A writing template or the practice project's suggestion. | Use it as a starting point; read and edit the task before starting. |
| Task | One concrete change, expected behavior, and what must be preserved. | “Reject blank names, show a clear message, and add focused tests.” |
| Checks | An actual check found in the project. | Keep the recommended choice if it matches the work. |
| Model routing | The role arrangement for the run. | Smart unless you intentionally configured Manual. |
| Advanced options | Optional search hint and run limits. | Keep defaults for the first task. |

Starting points include **Write my own task**, **Fix a problem**, **Add a feature**, **Improve the checks**, and **Make something easier to use**. A template fills in useful wording. Replace every bracketed prompt with your own instructions before starting. If you have already edited the Task text, choosing another starting point keeps that draft; save a copy and empty the field first if you intend to insert a different template. A template is not a different execution mode and does not start work by itself. Be specific about the behavior you want. Include examples when they clarify the result. Keep credentials and private customer data out of the request.

Select **Start task** once. The app validates required settings, saves the task, and starts work. If a required account or project is unavailable, it names the problem instead of inventing a run. A second active task is not started while the current operation is still active.

### Advanced task options

| Option | Purpose | Default and limits |
| --- | --- | --- |
| Search term | A literal function name or term that helps find relevant code. | Optional; up to 300 characters. |
| Build attempts | Limits the bounded attempts to produce acceptable work. | 3; choose 1–5. |
| Model requests | Caps model calls made by the run, including scouts and reviews. | 24; choose 8–60. |
| Check timeout, seconds | How long an individual check process may run. | 120 seconds; choose 10–600. |

These limits prevent an unbounded loop. A request-count limit is not a dollar budget. Provider costs depend on the actual provider plan and use. A timeout for tests does not mean the whole coding task must finish in that time.

Once the run is saved, its task settings stay fixed. Use **Revise task** to change the request, checks, or limits in a new run with the old entries already filled in.

<a id="checks"></a>
## Checks and test commands (Or: “It said PASS” is not enough)

Checks are the project's own automated ways to test behavior. The picker reads project files and shows supported choices with their source. Select the check that actually covers the intended change.

For an explicit command, choose **Advanced — use my own check command** in **Checks** and enter the test tool directly in **Custom check command**. The command can be up to 1,000 characters. Examples of single commands are:

```text
python3 -m unittest discover -s tests -v
python3 -m pytest -q
npm test
cargo test
```

Only use a command appropriate to the selected project. These are examples, not a promise that every project has all four tools installed.

Enter one command without `&&`, pipes, redirection, or shell wrappers. An installation command is not a check command. For example, do not enter `npm install && npm test` or `npx vitest`. The project maintainer prepares dependencies first; RATBAG runs the selected installed checks in its separate working copy.

### What counts as a pass

The command must exit successfully and supply recognized evidence that tests ran. RATBAG records the output and distinguishes an actual pass from “no tests” or an unknown result. A reviewer's approval cannot convert a failing process into a pass.

A check result proves what that command tested. It does not automatically prove visual correctness, production compatibility, or behavior the tests never exercised. The current application does not automatically capture browser screenshots or run a visual audit.

For a custom test program, an operator can supply the supported explicit summary marker `SWARM_TESTS=<count>`, where the count is the number of actual checks performed. It must be a positive count, and the program must exit successfully only when its checks pass. Do not print invented counts merely to satisfy the gate.

<a id="workspace"></a>
## Follow the workspace (Or: The work has a paper trail)

| Panel | What it shows | What you can open |
| --- | --- | --- |
| Task heading | Saved request, current state, identifying details, and run controls. | The available control for the present state. |
| Builder | The current stage and its recorded explanation. | **View evidence**. |
| Architect | Plan, recovery, and final review checkpoints. | The saved review for a completed checkpoint. |
| Routing | The chosen next step or check command and its recorded reason. | The complete routing decision. |
| Review desk / Saved checks | Recorded checks and quick access to saved files in layouts with a review area. | **Open saved evidence** or a listed evidence file. |
| Find files | Files located for the task. | **View findings**. |
| Find references | Matching code and references. | **View findings**. |
| Tests & review | Recorded checks and the auditor's review. | **View checks**. |
| Activity | Events as the task proceeds. | An event's details and related evidence. |
| Outcome | What is available at the end or what action is needed. | **Download patch** when the completed result is available. |

The Architect is called at meaningful review points, so it may be waiting while the Builder works. The two scout requests can proceed in parallel. The app runs one coding task at a time.

In **Activity**, **Follow latest** keeps the newest activity in view. Turn it off to read earlier entries without jumping to the newest one. **Show earlier** reveals earlier events when available. The event count describes recorded events, not percentage completion.

The app retains full saved evidence. Concise panel messages are summaries. Open the evidence when a decision, failed check, or proposed change needs closer inspection. File discovery identifies actual files; it is not a claim that every language has been parsed into a full code-structure map.

<a id="states"></a>
## Task states and controls (Or: Know what “done” means)

| State or message | What it means | Your next action |
| --- | --- | --- |
| Queued | The request is saved and waiting for its worker to begin. | Wait for the stage to update. |
| Running | A real stage is active. | Follow the evidence; Pause or Stop if needed. |
| Pause requested | The current operation has not reached a safe boundary yet. | Wait for Paused; do not assume it has already stopped. |
| Paused | The saved run is no longer advancing. | Select Resume when ready. |
| Stop requested | The app is ending the active work. | Wait until the operation ends and Stopped appears. |
| Stopped | This run has ended at your request. | Inspect saved work or select Revise task for a new run. |
| Interrupted | The server stopped before the run finished. | Restore any missing account entries, then Resume when offered. |
| Needs input | A specific problem requires correction. | Read the next action. Repair external/account issues and Resume, or Revise task if its settings must change. |
| Failed | The run could not reach an acceptable result within its allowed work. | Read the last failure and reviews, then Revise task with a focused correction. |
| Ready for review | This exact candidate passed the recorded checks and required reviews, and its patch is saved. | Read the evidence and Download patch. |

**Pause** saves completed work and waits for a safe boundary. **Stop** ends the run while retaining evidence. Neither button deletes the project or history. An in-flight provider response can take time to finish or time out; the app reports the requested state while it waits.

**Resume** reuses saved progress and its fixed starting copy. It does not apply a new task description to old evidence. **Revise task** is the control for changing the task itself. The old run remains in History.

If you change the team's model settings while the task is paused, selecting **Resume** uses your current saved choices. The activity record keeps both the previous and current assignments, alongside the earlier plans, checks, and changes.

<a id="evidence"></a>
## Evidence, downloads, and handoff (Or: Keep the receipts)

Open **View evidence**, **Open saved evidence**, or an event to open the evidence. Choose a saved item in its list. You can inspect the full text and use **Download** for that item. In most layouts, evidence opens in a drawer. Ultrawide keeps it on a permanent evidence desk; its **Expand evidence** button opens a larger view, and closing that view returns it to the desk.

The evidence may include the selected source files, plan, review decisions, routing decision, proposed patches, patch-application diagnostics, check output, and the final result record. Some records contain structured labels intended to be exact; use the panel's plain-language description to understand why they matter.

| Item | Why it is useful |
| --- | --- |
| Plan review | Shows whether the Architect accepted the proposed approach before building. |
| Attempt patch and diagnostics | Shows exactly what was proposed and why an unsuccessful attempt failed. |
| Check output | Shows what the actual process printed and whether tests ran. |
| Auditor review | Records the auditor's assessment of that candidate. |
| Final review | Records the Architect's final decision about the same tested candidate. |
| Final patch and identity | Keeps the downloadable changes tied to the tested and reviewed version. |

When **Download patch** appears, it downloads the preserved final patch. A patch is a text file describing edits, not a replacement project folder. Downloading it does not commit, merge, push, or publish anything. The original project stays unchanged by the run.

On iPhone or iPad, use the browser's download or share controls to save it in **Files**. Keep the task identifier with the patch so a maintainer can find the same run and its evidence later. The app also retains the successful candidate working copy on the server.

For a novice handoff, provide the patch and the run's check and final-review evidence to the person maintaining the project. Applying and publishing the changes follows that project's existing process; this release does not contain an Apply or Publish button.

<a id="history"></a>
## History and revised tasks (Or: Yesterday's work still exists)

Open **History**, then select a run to return to its workspace and saved evidence. A completed run does not become an active task merely because you opened it. A run's task text, state, and identifying details help you choose the correct one.

Select **Revise task** when you want to try again with a narrower request, different check command, updated project state, or different limits. Read the prefilled fields, change the necessary entries, and select **Start new run** to create the new run.

Use Resume for a recoverable pause or interruption when the request itself is still correct. Use Revise task when the request or its settings need to change. Repeatedly resuming an unchanged request will not fix an unsuitable test command or increase its budget.

History and evidence survive browser closure. They survive a server restart when the service retains its data folder. The app does not automatically delete failed attempts or old workspaces. The operator maintains storage and backups.

<a id="appearance"></a>
## Themes and device layouts (Or: Your screen gets a vote)

Open **View** to reach **Your screen. Your setup.** and its appearance controls. These choices apply to that browser and are remembered there. They do not affect task behavior, model selection, or provider usage.

### Themes

| Choice | Result |
| --- | --- |
| System | Follows the device's light or dark appearance preference. |
| Dark | Charcoal surfaces with restrained blue accents. |
| Light | Light surfaces and darker text for a brighter workspace. |
| High contrast | Stronger separation, text, borders, and focus visibility. |

RATBAG's mascot keeps its safety-orange waist pack in every theme. The background, surrounding lettering, and contrast adapt with System, Dark, Light, or High contrast. This is part of the theme selection; there is no separate mascot setting.

Help pages offer the same theme choices. They share the app's saved theme on the same browser and address. Device reduced-motion settings are respected. If browser storage is unavailable, the current page can still use a theme; it may need to be selected again next visit.

### Layouts

| Choice | Intended use |
| --- | --- |
| Automatic | Lets the app select the appropriate workspace arrangement for the current display. |
| iPhone | Focused Work, Team, Activity, and More views. Navigation sits along the bottom in portrait and moves to the side in landscape. Designed for phone use including iPhone 16 Pro. |
| iPad | A project shelf above the work areas, with Work and Activity beside Team and Review. Landscape gives the work area more room. Designed for iPad use including iPad A16. |
| Desktop | Architect and Projects on the left, the building and checking flow beside them, and Activity across the bottom. |
| Widescreen | Separate areas for Projects, Work and Activity, and Architect with the Review desk. |
| Ultrawide | Projects and Saved checks on the left, Work and Activity in the middle, and Architect with a permanent evidence desk on the right. |

These are workspace arrangements, not an instruction to zoom out until a desktop page fits a phone. You can explicitly choose a profile or return to Automatic. If a manually selected layout feels cramped, choose the profile for the current device. Turning the device or resizing the window still adjusts the selected arrangement's available space.

Use the browser's normal text-size or zoom controls when needed. The app provides visible keyboard focus, labelled form controls, and close buttons for dialogs. Keyboard users can move through controls with Tab and activate focused buttons with Enter or Space. Do not depend on colour alone; status labels and text explain the state.

<a id="advanced-models"></a>
## Advanced model settings (Or: Open the bonnet only when you need to)

Open **Models → Advanced** to inspect a role's individual connection. Open the role, choose a listed entry in its **Model** dropdown, then select **Save role**. The list supplies matching connection settings without requiring you to type model identifiers. Keep the defaults for a first run.

Choose **Custom model / connection** when the operator has a different supported service. Open **Custom connection and limits** to inspect the exact settings. Changing a dropdown is not enough by itself: save the role before checking the changed connection.

| Setting | Plain meaning |
| --- | --- |
| Role | Which job this model performs. |
| Model | A listed model choice or Custom model / connection. |
| Provider profile | A starting connection preset for the selected provider. Review the address and format before saving. |
| Model ID | The provider’s exact model identifier. A product’s release title may differ from its API name. |
| API format | The request format the provider accepts: OpenAI-compatible or Anthropic-compatible. It does not select a subscription by itself. |
| Provider address | The provider service address, without a key or secret in it. |
| Reasoning effort | The provider-supported effort setting for that role. |
| Maximum output tokens | Maximum response allowance for that request; the provider determines how its reasoning and text use that allowance. |
| Connection timeout, seconds | How long the client waits for the provider request; choose 1–600 seconds. This is different from the check-process timeout. |
| Environment key name | The server-environment variable from which this role can read a key. This is the variable's name, not the secret itself. |
| Session API key | A key supplied to this running server, held in its memory. |
| Enabled | Whether this role is available for new tasks. All four core roles must be enabled; the optional Router role can stay off. |
| Save role / Check connection | Save the role's settings, then explicitly verify its current connection. |

Both native GLM models are locked to the requested international Coding address:

```text
https://api.z.ai/api/coding/paas/v4
```

The server enforces that choice. The endpoint selection does not independently certify a physical US storage location. The default DeepSeek and MiniMax addresses are `https://api.deepseek.com/v1` and `https://api.minimax.io/v1`. The optional Optional router address is `https://openrouter.ai/api/v1`.

Save a changed role, then check it. Changing its address or connection format can clear the old session key so a secret is not accidentally sent to a different service. Re-enter the correct account key if the status shows it is missing. Saving a core role automatically selects Manual routing to keep its custom settings for the next task. Saving the optional Router role leaves the core routing mode unchanged. You can deliberately choose Smart again to restore its preset.

The server refuses model-setting changes while a task is active. Wait until it finishes or request Stop and wait for the operation to end before changing the configuration.

<a id="recovery"></a>
## Recovery (Or: Fix the cause, keep the work)

Read the task's next-action message and the related evidence first. Use the matching row below. Failed work is retained; there is no need to delete history to try again.

| Problem | What to do |
| --- | --- |
| A required model key is missing | Open Models → Accounts, save that account's key, and check the core models. Start the unsent task, or Resume a saved run when offered. |
| A provider rejects the key or reports it expired | Replace that account entry with a valid key and check again. If it is optional Router, leave that connection disabled until corrected. |
| A provider has no credit or access to the selected model | Correct the account/plan with that provider, or intentionally choose a supported Manual arrangement. Check the current settings before continuing. |
| Provider request timed out or the network failed | Restore connectivity and check the affected role. Resume if the saved request remains correct. Do not assume the interrupted request was free or automatically repeated. |
| A project folder is missing | Select an existing server project. Ask the operator to restore or place it in the configured project folders if needed. |
| No check command was found | Select a discovered check or the custom-command option in Checks, enter the project’s actual installed command, then start a revised task. |
| Check command contains unsupported shell syntax | Replace it with one installed test tool and its arguments. Prepare dependencies separately. Use Revise task for a saved run. |
| Test tool or project library is missing | Have the project maintainer prepare the project environment on the server. Then Resume if no task setting changed, or Revise task if the command changed. |
| “No tests” or an unknown check result | Choose a command that runs actual tests and reports their results. A zero exit code alone is insufficient. Start a revised task with that command. |
| Tests exceeded the timeout | Inspect the output for a stuck process. If the suite is legitimately longer, choose Revise task and set an appropriate timeout within the allowed range. |
| Patch could not be applied | Read the saved patch diagnostic. The Builder can repair it within the run limits. If the run ends, use Revise task with a smaller or more specific request. |
| Architect or auditor rejected the work | Read the listed issues. The app prevents advancement and can attempt a bounded repair. Use Revise task if the saved run cannot resolve it. |
| Model-request or build-attempt limit reached | Inspect the last result, narrow the task where possible, and choose Revise task. Increase a limit deliberately only if the extra work is justified. |
| Required source/evidence is too large | Split the work into a smaller change and name the relevant function or file. The Builder needs complete source alongside its plan and repair evidence. |
| The saved candidate changed after checking | Inspect the retained candidate. Start a new run; earlier checks cannot prove the new file contents. |
| A template still contains bracketed prompts | Replace the bracketed descriptions with your actual instructions, then select Start task. Your entered draft remains in the form. |
| Another task is still active | Return to that run. Wait, or request Stop and wait until it ends, before starting another. |
| Server restarted | Reconnect, restore session-only keys if needed, open History, and Resume an interrupted run when offered. |
| Ready result has no visible change in the original project | Expected: the app prepares a separate candidate and downloadable patch. Hand the patch to the project maintainer for review and application. |
| Download did not appear | Open the browser's Downloads or Files destination, then use Download again from the same completed run if necessary. |

<a id="connection-recovery"></a>
## Connection recovery (Or: Is there anybody on the other end?)

| What opens? | Next action |
| --- | --- |
| Neither the server nor RATBAG | Restore the device's access to the private the server network. If other devices can reach it, compare the current device's network connection. |
| the server opens, but `/swarm/` does not | The the server operator should check the RATBAG service and the server route. Your model keys are not the cause of a missing web page. |
| RATBAG opens and asks for Server access | Enter the RATBAG access key provided by the operator, then select Connect. |
| The interface opens but reports a lost connection | Restore the connection and select Reconnect. Reopen History to retrieve the current state. |
| Other controls work, but one provider check fails | Read that role's message in Models. Fix that provider account or connection rather than restarting unrelated work. |

Keep the task identifier and the exact visible message when asking the operator for help. You do not need to send the model key with a screenshot or paste it into an error report.

<a id="boundaries"></a>
## Saved work and current boundaries (Or: The useful truth)

RATBAG saves run history, settings without keys, patches, check output, and review evidence. Failed proposals and separate workspaces are retained. There is no automatic delete or destructive cleanup control.

The current release builds text additions and edits. File deletion, moving files, binary-file changes, symlink changes, and submodule changes require a different workflow. If a request requires those changes, narrow this run to the supported part and have the maintainer handle the rest deliberately.

The Builder has a measured input-content size limit. It preserves whole selected source files and needed review evidence; it does not pretend that omitted code was read. The ordinary file searches are not a full language-aware analysis of every possible invariant.

Use trusted projects. The separate Git working copy protects the original files from the app's normal editing flow, but it is not a virtual machine that confines malicious test code. The operator maintains the server environment, backups, and project dependencies.

The app does not automatically merge, push, publish, apply patches to the original project, evaluate model prices, or perform a browser screenshot audit. The visible controls correspond to what it actually runs and saves.

<a id="using-help"></a>
## Use the guides (Or: The manual has controls too)

**Help → QuickStart** and **Help → User manual** open in a separate browser tab, leaving the workspace available. The guide header links to **Help home**, **QuickStart**, **User manual**, and **Find a feature**. The side links include **Back to RATBAG**, **Run guided setup**, and **Installation guide**.

Enter a word or phrase in **Find a topic in this guide** to show matching sections. The section count tells you how much matches. **Clear search** restores the full guide. Selecting a heading jumps to that section. Use the browser’s own Find command if you want to locate a particular word inside a long matching section.

The **Theme** menu shares the workspace’s appearance preference on the same browser and address. **Print or save as PDF** opens the browser’s print controls with the guide formatted for paper. Choose your device’s PDF option if you want an offline copy. These help controls make no provider requests.

To return to a workspace whose access key is already entered, switch back to the original RATBAG tab. Following Back to RATBAG opens the app in the current tab and may ask for its access key again.

<a id="glossary"></a>
## Small glossary (Or: The words behind the buttons)

| Word | Meaning here |
| --- | --- |
| Account key | A provider-issued secret that lets RATBAG make model requests on that account. |
| Server access key | A different key that opens this RATBAG installation. |
| Provider | The service supplying a model, such as GLM, DeepSeek, or MiniMax. |
| Model | The software doing an assigned language or coding job. |
| Project / repository | A folder of project files managed with Git. |
| Run | One saved attempt to complete a task under fixed settings. |
| Candidate | A separate proposed version of the project being checked. |
| Patch | A text file describing the edits. |
| Evidence | Saved source, decisions, proposed edits, or actual check results supporting the run. |
| Check / test | An automated program used to verify selected behavior. |
| Snapshot | The fixed starting copy used by a run. |
| Hash / SHA-256 | A content fingerprint used to identify the exact saved version. |
| Model request | One call to a configured model service; a run can make several. |

**DOCUMENT ENDS**

*Floyd Labs — The Garage Desk*

*Keep the controls close. Keep the evidence closer. Leave the PowerPoint in the car.*

| Garage notes | Status |
| --- | --- |
| Bella | Large black cat; requires room for proper supervision |
| Bowser | Smaller black cat; first to the router, as usual |
| Coffee | Working despite serious flavour concerns |
| The dark side | A theme choice, not a prerequisite |
