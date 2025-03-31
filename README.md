# QtCelestial

QtCelestial is a project aimed at making a browser capable of being used as a daily browser.

### NOTICE
I haven't tested on any other os other than Arch Linux, i don't currently know how to use Tor Mode on Windows

##  Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Contributing](#contributing)
- [Requirements](#requirements)

## Installation

To install QtCelestial, follow these steps:

1. Clone the repository:
   git clone https://github.com/boykissah/qtcelestial.git

    Navigate to the project directory:
    cd qtcelestial

Install the required dependencies:
  pip install PyQt6 PyQt6-WebEngine stem python-socks
## Requirements
   
- Python 3.8 or higher
- PyQt6 and PyQt6-WebEngine
- Tor (external installation required)
- stem library for Tor control
- python-socks for SOCKS proxy support
  
## Usage

To use QtCelestial, follow these steps:

    python main.py  
    sudo tor (If you're going to use Tor Mode)
## Features

    Feature 1: Multiple Tabs
    Feature 2: Download Manager
    Feature 3: Saves cookies locally, does not share data.
    Feature 4: Tor support

## Contributing

We welcome contributions! Please follow these guidelines:

    Fork the repository.
    Create a new branch (git checkout -b feature-branch).
    Make your changes.
    Commit your changes (git commit -m 'Add some feature').
    Push to the branch (git push origin feature-branch).
    Open a pull request.
