import google.generativeai as genai
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import random

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Configure safety settings to be more permissive for web scraping content
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_ONLY_HIGH"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_ONLY_HIGH"
    }
]

# Rate limiting globals
_last_request_time = 0
_request_lock = threading.Lock()
_request_count = 0
_request_window_start = 0

def wait_for_rate_limit():
    """Implement rate limiting to respect API quotas"""
    global _last_request_time, _request_count, _request_window_start
    
    with _request_lock:
        current_time = time.time()
        
        # Reset counter if window has passed (60 seconds)
        if current_time - _request_window_start > 60:
            _request_count = 0
            _request_window_start = current_time
        
        # If we're approaching the limit (8 out of 10), add delay
        if _request_count >= 8:
            wait_time = 60 - (current_time - _request_window_start) + 1
            if wait_time > 0:
                print(f"⏳ Rate limit protection: waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                _request_count = 0
                _request_window_start = time.time()
        
        # Ensure minimum delay between requests
        time_since_last = current_time - _last_request_time
        min_delay = 6.5  # Slightly more than 60/10 to be safe
        if time_since_last < min_delay:
            delay = min_delay - time_since_last + random.uniform(0.5, 1.5)  # Add jitter
            time.sleep(delay)
        
        _last_request_time = time.time()
        _request_count += 1

model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=safety_settings)

# Generation configuration
generation_config = {
    "temperature": 0.1,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 4096,  # Increased to handle larger responses
}

template = (
    "Extract only the information that matches this description: {parse_description}\n\n"
    "From this content: {dom_content}\n\n"
    "Rules:\n"
    "- Return only the requested data\n"
    "- No explanations or extra text\n"
    "- If no match found, return empty string\n"
    "- Be concise and direct\n\n"
    "Response:"
)


def process_single_chunk(chunk_data):
    """Process a single chunk with rate limiting and retry logic"""
    chunk_index, chunk, parse_description = chunk_data
    
    prompt = template.format(dom_content=chunk, parse_description=parse_description)
    
    # Try up to 3 times for each chunk with exponential backoff
    for attempt in range(3):
        try:
            # Apply rate limiting before making request
            wait_for_rate_limit()
            
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Check if response has valid content
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                
                # Check finish reason
                if candidate.finish_reason == 1:  # STOP - normal completion
                    if candidate.content and candidate.content.parts:
                        result = candidate.content.parts[0].text.strip()
                        print(f"✓ Processed chunk {chunk_index + 1}")
                        return chunk_index, result
                    else:
                        print(f"⚠ Chunk {chunk_index + 1}: No content in response")
                        if attempt == 2:  # Last attempt
                            return chunk_index, ""
                        continue
                        
                elif candidate.finish_reason == 2:  # MAX_TOKENS
                    print(f"⚠ Chunk {chunk_index + 1}: Response truncated (taking partial result)")
                    if candidate.content and candidate.content.parts:
                        result = candidate.content.parts[0].text.strip()
                        return chunk_index, result
                    else:
                        if attempt == 2:
                            return chunk_index, ""
                        continue
                        
                elif candidate.finish_reason == 3:  # SAFETY
                    print(f"⚠ Chunk {chunk_index + 1}: Blocked by safety filters")
                    return chunk_index, ""
                    
                elif candidate.finish_reason == 4:  # RECITATION
                    print(f"⚠ Chunk {chunk_index + 1}: Blocked due to recitation")
                    return chunk_index, ""
                    
                else:
                    print(f"⚠ Chunk {chunk_index + 1}: Unknown finish reason: {candidate.finish_reason}")
                    if attempt == 2:
                        return chunk_index, ""
                    continue
            else:
                print(f"⚠ Chunk {chunk_index + 1}: No candidates in response")
                if attempt == 2:  # Last attempt
                    return chunk_index, ""
                continue
                
        except Exception as e:
            error_msg = str(e)
            
            # Handle rate limit errors specifically
            if "429" in error_msg or "quota" in error_msg.lower():
                # Extract retry delay if available
                retry_delay = 20  # Default retry delay
                if "retry in" in error_msg:
                    try:
                        # Extract the retry delay from the error message
                        import re
                        match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                        if match:
                            retry_delay = float(match.group(1)) + 1  # Add 1 second buffer
                    except:
                        pass
                
                print(f"⏳ Chunk {chunk_index + 1}: Rate limit hit, waiting {retry_delay:.1f}s before retry {attempt + 1}/3")
                time.sleep(retry_delay)
                continue
            
            # Handle other errors with exponential backoff
            else:
                wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)  # Exponential backoff with jitter
                print(f" Error processing chunk {chunk_index + 1} (attempt {attempt + 1}/3): {error_msg}")
                if attempt < 2:  # Not the last attempt
                    print(f"⏳ Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    return chunk_index, ""
    
    return chunk_index, ""


def parse_with_gemini(dom_chunks, parse_description, max_workers=2, progress_callback=None):
    """
    Process multiple chunks in parallel using ThreadPoolExecutor with rate limiting
    
    Args:
        dom_chunks: List of text chunks to process
        parse_description: Description of what to extract
        max_workers: Maximum number of concurrent threads (default: 2 for free tier)
        progress_callback: Function to call with (completed, total) for progress updates
    """
    # For free tier, limit workers to avoid rate limits
    if max_workers > 3:
        print(f"⚠ Limiting workers to 3 to respect API rate limits (requested: {max_workers})")
        max_workers = 3
    
    print(f" Starting rate-limited parallel processing of {len(dom_chunks)} chunks with {max_workers} workers...")
    print(f" Free tier limit: 10 requests/minute - estimated time: {len(dom_chunks) * 7}s")
    
    # Prepare chunk data for parallel processing
    chunk_data_list = [(i, chunk, parse_description) for i, chunk in enumerate(dom_chunks)]
    
    # Store results with their original index
    results = {}
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_chunk = {
            executor.submit(process_single_chunk, chunk_data): chunk_data[0] 
            for chunk_data in chunk_data_list
        }
        
        # Collect results as they complete
        completed = 0
        for future in as_completed(future_to_chunk):
            chunk_index = future_to_chunk[future]
            completed += 1
            try:
                index, result = future.result()
                results[index] = result
                print(f" Progress: {completed}/{len(dom_chunks)} chunks completed")
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, len(dom_chunks))
                    
            except Exception as exc:
                print(f"❌ Chunk {chunk_index + 1} generated an exception: {exc}")
                results[chunk_index] = ""
                
                # Still update progress even for failed chunks
                if progress_callback:
                    progress_callback(completed, len(dom_chunks))
    
    # Sort results by original index and filter out empty ones
    sorted_results = [results[i] for i in sorted(results.keys())]
    non_empty_results = [result for result in sorted_results if result.strip()]
    
    print(f"✅ Completed! Processed {len(non_empty_results)} chunks with content out of {len(dom_chunks)} total")
    return "\n".join(non_empty_results)


# Alias for backward compatibility and progress support
def parse_with_gemini_progress(dom_chunks, parse_description, max_workers=2, progress_callback=None):
    """Progress-enabled version of parse_with_gemini (same function with different name for clarity)"""
    return parse_with_gemini(dom_chunks, parse_description, max_workers, progress_callback)