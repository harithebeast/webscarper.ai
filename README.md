# **Web Scraper AI**

A powerful web scraping tool powered by Llama 3.1. This project leverages advanced natural language processing capabilities to intelligently extract and process data from websites.

---

## **Prerequisites**

Before cloning and running this project, ensure the following are installed on your system:

1. **[Ollama](https://ollama.com)**  
   - Ollama is required to manage and run Llama 3.1 locally.  
2. **Llama 3.1**  
   - Install Llama 3.1 via Ollama to enable AI functionalities.  

---

## **Installation**

Follow these steps to set up and run the project:

```bash
# Step 1: Clone the repository
git clone https://github.com/harithebeast/webscarper.ai.git
cd webscarper.ai

# Step 2: Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install the required Python packages
pip install -r requirements.txt

# Step 3: Verify Ollama and Llama 3.1 Installation
# Ensure Ollama is running, and Llama 3.1 is available
ollama list

# If Llama 3.1 is not listed, install it
ollama pull llama3.1

# Step 4: Configure the Project
# Update the `config.json` file to customize scraping parameters like URLs, data fields, and output formats.
