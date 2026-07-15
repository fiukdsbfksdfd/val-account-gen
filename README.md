# Account Generator

An automated account generator for that tactical shooter that rhymes with *Balorant*.

> **Note**
> This project is no longer actively maintained. I replaced it with a much faster API-based system capable of significantly higher throughput. The source remains available for anyone interested in learning from it or building their own version.

---

## Preview

![Startup](start.png)

![Generated Account](generated.png)

---

# Quick Start

### Pre-compiled Binary

If you don't want to build from source, simply download the latest release.

**Requirements**
- Google Chrome must be installed.
- Do **not** use Cloudflare WARP or a VPN.
- Your IP needs to not be flagged by smailpro (if it needs captcha ur cooked)

## Downloads

### Latest Release
[Click Me](https://github.com/<OWNER>/<REPO>/releases/latest)

### Chrome
[Click Me](https://www.google.com/chrome/dr/download/)

---

## Installation

1. Download the latest executable from the Releases page.
2. Launch the program.
3. Follow the prompts and start generating accounts.

> **Common Issues**
>
> If the generator fails immediately, the most common cause is SMailPro requiring a CAPTCHA for your IP.
>
> - Do **not** use WARP.
> - Do **not** use a VPN.
> - If your IP is flagged, either complete the CAPTCHA manually or use your own proxy/CAPTCHA-solving solution.

---

# How It Works

The generator performs the following steps automatically:

- Opens **Google Chrome**.
- Visits SMailPro and retrieves a temporary email.
- Opens the account registration page.
- Fills in the email address.
- Waits for the verification email.
- Retrieves the verification code.
- Completes registration.
- Generates a random username and password.

---

# Notes

- The default configuration is intended for North America.
- Some regions may use different URLs or CAPTCHA behavior.
- If needed, modify the source to use your own proxy or CAPTCHA-solving API.

---

# Credits

About 90% of this project was written by GLM 5.2.

If you fork or reuse this project, please keep the original credits intact.

---

# Disclaimer

This repository is provided for educational and research purposes only.
