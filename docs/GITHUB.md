# Push this project to GitHub

Extract the download and open Terminal in the `Compresso` folder. Create an
**empty** repository on GitHub called `compresso`; leave README, .gitignore and
license initialization unchecked. Choose public/private visibility as desired.

Replace `YOUR_USERNAME` below with your GitHub username:

```bash
git init -b main
git add .
git update-index --chmod=+x start Start-Compresso.command
git commit -m "Initial commit: Compresso with demo samples"
git remote add origin https://github.com/YOUR_USERNAME/compresso.git
git push -u origin main
```

GitHub command-line authentication must be configured. For HTTPS, use a personal
access token if Git asks for a password; do not use your GitHub account password.

If Git asks for your author identity, set it and retry the commit:

```bash
git config --global user.name "Your Name"
git config --global user.email "YOUR_GITHUB_EMAIL"
```

For later changes:

```bash
git add .
git commit -m "Describe your changes"
git push
```

Source and samples are included. Dependencies, virtual environments, build
artifacts, local outputs and environment files are ignored. Each sample file is
under 7 MB, so this pack does not need Git LFS.

[GitHub's official import instructions](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
