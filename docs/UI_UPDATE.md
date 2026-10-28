# Compresso 2.1 UI and launch update

- The download arrow and all six rings share a single layout anchor. The rings
  pulse without drifting off-center, including while processing.
- The title and controls sit below the smallest ring.
- Scrollbars use a dark rail and rounded muted-purple thumb, with lavender hover
  and pressed states. Vertical and horizontal scrollbars share this treatment,
  including Artifact Lens and other nested scroll areas.
- Open `Start-Compresso.command` in Finder to launch. From Terminal, use `./start`.
  The launcher sets up the local Python environment and npm dependencies once,
  and refreshes them when the requirements or lockfile change. Installation
  requires internet; subsequent file processing is local.

The archive contains source, not a prebuilt Mac app. macOS Finder execution,
native scrollbar behavior, and installer packaging still require a Mac check.

The separate sample pack includes a START_HERE.md walkthrough and reproducible
fixtures for each tool. Existing setup and build commands remain available.
