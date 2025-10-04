import streamlit as st
import time
from scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    split_dom_content,
)
from parse import parse_with_gemini, parse_with_gemini_progress

# Streamlit UI
st.title("AI Web Scraper")
url = st.text_input("Enter Website URL")

# Check if URL has changed and clear previous content
if url and 'current_url' in st.session_state and st.session_state.current_url != url:
    # Clear previous scraping data when URL changes
    if 'dom_content' in st.session_state:
        del st.session_state.dom_content
    if 'parsed_results' in st.session_state:
        del st.session_state.parsed_results
    st.info("🔄 New URL detected - previous content cleared")

# Store current URL
if url:
    st.session_state.current_url = url

# Step 1: Scrape the Website
if st.button("Scrape Website"):
    if url:
        # Create progress bar and status
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("🌐 Initializing web scraper...")
            progress_bar.progress(0.10)  # 10%
            
            status_text.text("🔍 Scraping the website...")
            progress_bar.progress(0.30)  # 30%
            
            # Scrape the website
            dom_content = scrape_website(url)
            progress_bar.progress(0.60)  # 60%
            
            status_text.text("📄 Extracting content...")
            body_content = extract_body_content(dom_content)
            progress_bar.progress(0.80)  # 80%
            
            status_text.text("🧹 Cleaning content...")
            cleaned_content = clean_body_content(body_content)
            progress_bar.progress(0.90)  # 90%

            # Store the DOM content and URL in Streamlit session state
            st.session_state.dom_content = cleaned_content
            st.session_state.scraped_url = url
            st.session_state.scrape_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            progress_bar.progress(1.0)  # 100%
            status_text.text(" Scraping completed successfully!")
            
            st.success(f" Successfully scraped: {url}")
            
            # Display the DOM content in an expandable text box
            with st.expander("View DOM Content"):
                st.text_area("DOM Content", cleaned_content, height=300)
                
        except Exception as e:
            progress_bar.progress(0.0)  # 0%
            status_text.text(" Scraping failed!")
            st.error(f"Error scraping website: {str(e)}")


# Step 2: Ask Questions About the DOM Content
if "dom_content" in st.session_state:
    # Show which website's content we're about to parse
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f" Ready to parse content from: **{st.session_state.get('scraped_url', 'Unknown URL')}**")
        st.caption(f"Scraped at: {st.session_state.get('scrape_timestamp', 'Unknown time')}")
    with col2:
        if st.button(" Clear", help="Clear scraped content and start fresh"):
            for key in ['dom_content', 'scraped_url', 'scrape_timestamp', 'parsed_results', 'current_url']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    parse_description = st.text_area("Describe what you want to parse")
    
    # Add a slider for controlling parallel processing
    col1, col2 = st.columns(2)
    with col1:
        max_workers = st.slider(
            "Parallel Workers", 
            min_value=1, 
            max_value=5, 
            value=2, 
            help="Number of parallel threads. Free tier: max 3 workers recommended to avoid rate limits."
        )
    with col2:
        if max_workers > 3:
            st.warning(f" {max_workers} workers may hit rate limits on free tier")
        else:
            st.info(f" {max_workers} workers - good for free tier")
        
        estimated_time = len(st.session_state.get('dom_content', '')) // 4000 * 7  # Rough estimate
        st.caption(f"Estimated time: ~{estimated_time}s")

    if st.button("Parse Content"):
        if parse_description:
            # Create progress tracking elements
            progress_col1, progress_col2 = st.columns([3, 1])
            
            with progress_col1:
                progress_bar = st.progress(0)
                status_text = st.empty()
            
            with progress_col2:
                progress_details = st.empty()
                time_elapsed = st.empty()
            
            # Start timing
            start_time = time.time()
            
            try:
                status_text.text(" Initializing parsing...")
                progress_bar.progress(0.05)  # 5%
                
                status_text.text(" Splitting content into chunks...")
                dom_chunks = split_dom_content(st.session_state.dom_content)
                progress_bar.progress(0.10)  # 10%
                
                progress_details.write(f"**📊 {len(dom_chunks)} chunks**")
                progress_details.write(f"**👥 {max_workers} workers**")
                
                # Create a custom progress callback
                def update_progress(completed, total):
                    elapsed = time.time() - start_time
                    # Convert to 0-1 scale for Streamlit progress bar
                    progress_percentage = min(0.9, 0.1 + (completed / total) * 0.8)  # 0.1 to 0.9
                    progress_bar.progress(progress_percentage)
                    
                    # Calculate ETA
                    if completed > 0:
                        eta = (elapsed / completed) * (total - completed)
                        status_text.text(f" Processing chunks... ({completed}/{total})")
                        time_elapsed.write(f"**⏱ {elapsed:.1f}s**")
                        if eta > 0:
                            time_elapsed.write(f"**🎯 ETA: {eta:.1f}s**")
                    else:
                        status_text.text("🤖 Starting AI processing...")
                        time_elapsed.write(f"**⏱️ {elapsed:.1f}s**")
                
                status_text.text(" Starting AI processing...")
                
                # Show a spinner while processing
                with st.spinner(" AI is thinking..."):
                    # Parse the content with Gemini using parallel processing
                    parsed_result = parse_with_gemini_progress(
                        dom_chunks, 
                        parse_description, 
                        max_workers=max_workers,
                        progress_callback=update_progress
                    )
                
                progress_bar.progress(0.95)  # 95%
                status_text.text("💾 Saving results...")
                
                # Store the parsed result
                st.session_state.parsed_results = parsed_result
                
                final_time = time.time() - start_time
                progress_bar.progress(1.0)  # 100%
                status_text.text("✅ Parsing completed successfully!")
                time_elapsed.write(f"**✅ Done in {final_time:.1f}s**")
                
                # Celebrate with balloons if it was successful
                st.balloons()
                
                st.success("✅ Parsing completed!")
                st.write("**Results:**")
                st.write(parsed_result)
                
            except Exception as e:
                progress_bar.progress(0.0)  # 0%
                status_text.text("❌ Parsing failed!")
                time_elapsed.write("**❌ Failed**")
                st.error(f"Error during parsing: {str(e)}")