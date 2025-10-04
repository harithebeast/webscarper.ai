# **Web Scraper AI**

A powerful web scraping tool powered by Google Gemini AI. This project leverages advanced natural language processing capabilities to intelligently extract and process data from websites.

---

## **Prerequisites**

Before cloning and running this project, ensure the following are set up:

1. **Google Gemini API Key**  
   - Sign up at [Google AI Studio](https://makersuite.google.com/app/apikey) to get your API key
   - You'll need this to access Google's Gemini AI model

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

# Step 3: Set up your Gemini API Key
# Create a .env file in the project root and add your API key:
echo "GEMINI_API_KEY=your_api_key_here" > .env

# Step 4: Run the application
streamlit run main.py
