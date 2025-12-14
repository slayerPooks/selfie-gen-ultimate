import os
import time
from pathlib import Path
from typing import List, Optional
import requests
import logging
from PIL import Image
import io
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FalAIKlingGenerator:
    def __init__(self, api_key: str, verbose: bool = True, model_endpoint: str = None, model_display_name: str = None):
        self.api_key = api_key
        self.verbose = verbose

        # Store model display name for logging
        self.model_display_name = model_display_name or "Kling 2.1 Professional"

        # Configurable model endpoint - defaults to Kling 2.1 Professional
        if model_endpoint:
            self.base_url = f"https://queue.fal.run/{model_endpoint}"
        else:
            self.base_url = "https://queue.fal.run/fal-ai/kling-video/v2.1/pro/image-to-video"

        # Freeimage.host guest API key
        self.freeimage_key = "6d207e02198a847aa98d0a2a901485a5"

        # Default prompt for head movement
        self.default_prompt = (
            "Turn head to the right slowly then all the way to the left slowly then to the right slowly, and to the left slowly. "
            "Make sure the body is kept still while doing this - ONLY turn THE HEAD NOT THE BODY. The subject should perform smooth, "
            "natural head movements with no body movement whatsoever. Keep shoulders, neck, and torso completely stationary. "
            "Head movements should be slow, deliberate, and realistic. Eyes can follow natural movement patterns. "
            "Maintain neutral facial expression throughout. Camera remains fixed and stationary. "
            "Generate in maximum resolution and professional quality with no blur, pixelation, or quality degradation."
        )

        # Downloads folder
        self.downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        
    def upload_to_freeimage(self, image_path: str) -> Optional[str]:
        """Upload image to freeimage.host"""
        try:
            img = Image.open(image_path)
            
            # Resize if needed
            max_size = 1200
            if img.width > max_size or img.height > max_size:
                if self.verbose:
                    logger.info(f"Resizing from {img.width}x{img.height}")
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to RGB
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Compress to JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            
            if self.verbose:
                logger.info(f"Uploading {Path(image_path).name} to freeimage.host...")
            
            response = requests.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": self.freeimage_key,
                    "action": "upload",
                    "source": image_base64,
                    "format": "json"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status_code') == 200:
                    url = result['image']['url']
                    if self.verbose:
                        logger.info(f"✓ Uploaded: {url}")
                    return url
            
            logger.error(f"Upload failed: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return None
    
    def check_duplicate_exists(self, image_path: str, output_folder: str = None) -> bool:
        """Check if video already exists in the target output folder"""
        try:
            char_name = Path(image_path).stem
            # Use provided output folder, or default to downloads folder
            target_folder = output_folder if output_folder else self.downloads_folder
            output_path = Path(target_folder) / f"{char_name}_kling.mp4"
            return output_path.exists()
        except Exception:
            return False
    
    def get_genx_image_files(self, folder_path: str, use_source_folder: bool = False,
                             fallback_output_folder: str = None) -> List[str]:
        """Get GenX images excluding duplicates

        Args:
            folder_path: Path to scan for images
            use_source_folder: If True, check for duplicates in source folder (image's parent)
            fallback_output_folder: Output folder to check for duplicates when use_source_folder=False
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
        genx_images = []

        try:
            for file_path in Path(folder_path).iterdir():
                if (file_path.is_file() and
                    file_path.suffix.lower() in image_extensions and
                    'genx' in file_path.name.lower()):

                    # Determine output folder for duplicate check
                    if use_source_folder:
                        check_folder = str(file_path.parent)
                    else:
                        check_folder = fallback_output_folder

                    if not self.check_duplicate_exists(str(file_path), check_folder):
                        genx_images.append(str(file_path))
                    elif self.verbose:
                        logger.info(f"Skipping duplicate: {file_path.name}")
        except Exception as e:
            if self.verbose:
                logger.error(f"Error getting GenX files: {e}")

        return genx_images
    
    def create_kling_generation(self, character_image_path: str, output_folder: str = None,
                                custom_prompt: str = None, use_source_folder: bool = False,
                                skip_duplicate_check: bool = False) -> Optional[str]:
        """Create Kling 2.5 Turbo Pro video via fal.ai

        Args:
            character_image_path: Path to source image
            output_folder: Fallback output folder (used when use_source_folder=False)
            custom_prompt: Custom generation prompt
            use_source_folder: If True, save video in same folder as source image
            skip_duplicate_check: If True, skip duplicate detection (for reprocessing)
        """
        try:
            # Determine actual output folder
            if use_source_folder:
                actual_output_folder = str(Path(character_image_path).parent)
            elif output_folder is not None:
                actual_output_folder = output_folder
            else:
                actual_output_folder = self.downloads_folder

            if not skip_duplicate_check and self.check_duplicate_exists(character_image_path, actual_output_folder):
                if self.verbose:
                    logger.info(f"Skipping {Path(character_image_path).name} - already exists")
                return None
            
            # Upload image
            image_url = self.upload_to_freeimage(character_image_path)
            if not image_url:
                logger.error("Failed to upload image")
                return None
            
            # Prepare prompt
            prompt = custom_prompt if custom_prompt else self.default_prompt
            
            # fal.ai API request
            headers = {
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Status check headers (no Content-Type for GET requests)
            status_headers = {
                "Authorization": f"Key {self.api_key}"
            }
            
            payload = {
                "image_url": image_url,
                "prompt": prompt,
                "duration": "10",
                "aspect_ratio": "9:16"
            }
            
            if self.verbose:
                logger.info(f"Creating {self.model_display_name} video via fal.ai...")
                logger.info(f"Image: {Path(character_image_path).name}")
                logger.info(f"Duration: 10 seconds")
                logger.info(f"Endpoint: {self.base_url}")
            
            # Submit request with retry logic
            max_submit_retries = 3
            request_id = None
            
            for submit_attempt in range(max_submit_retries):
                try:
                    response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
                    
                    if response.status_code == 429:
                        logger.warning(f"⚠ Rate limited - waiting before retry ({submit_attempt + 1}/{max_submit_retries})")
                        time.sleep(30)
                        continue
                    
                    elif response.status_code == 503:
                        logger.warning(f"⚠ Service unavailable - retrying ({submit_attempt + 1}/{max_submit_retries})")
                        time.sleep(10)
                        continue
                    
                    elif response.status_code == 402:
                        logger.error("💳 Payment required - insufficient credits in your fal.ai account")
                        return None
                    
                    elif response.status_code != 200:
                        logger.error(f"❌ Request failed: {response.status_code}")
                        logger.error(f"Response: {response.text}")
                        if submit_attempt < max_submit_retries - 1:
                            logger.info(f"Retrying... ({submit_attempt + 1}/{max_submit_retries})")
                            time.sleep(5)
                            continue
                        return None
                    
                    result = response.json()
                    request_id = result.get('request_id')
                    status_url = result.get('status_url')  # Get the status URL from response
                    
                    if not request_id or not status_url:
                        logger.error("✗ No request ID or status URL returned")
                        if submit_attempt < max_submit_retries - 1:
                            time.sleep(5)
                            continue
                        return None
                    
                    # Success!
                    break
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"⚠ Request timeout ({submit_attempt + 1}/{max_submit_retries})")
                    if submit_attempt < max_submit_retries - 1:
                        time.sleep(10)
                        continue
                    logger.error("✗ Failed to submit request after timeouts")
                    return None
                    
                except requests.exceptions.ConnectionError as e:
                    logger.warning(f"⚠ Connection error: {e} ({submit_attempt + 1}/{max_submit_retries})")
                    if submit_attempt < max_submit_retries - 1:
                        time.sleep(10)
                        continue
                    logger.error("✗ Failed to submit request due to connection errors")
                    return None
                    
                except Exception as e:
                    logger.error(f"✗ Unexpected error during submission: {e}")
                    if submit_attempt < max_submit_retries - 1:
                        time.sleep(5)
                        continue
                    return None
            
            if not request_id:
                logger.error("✗ Failed to get request ID after all retries")
                return None
            
            if self.verbose:
                logger.info(f"✓ Task created: {request_id}")
                logger.info("Waiting for video generation...")
            
            # Poll for completion with exponential backoff
            # Use the status_url provided by fal.ai (already authenticated)
            max_attempts = 240  # 20 minutes total (increased from 15)
            attempt = 0
            consecutive_errors = 0
            max_consecutive_errors = 10
            
            # Exponential backoff settings
            base_delay = 5
            max_delay = 30
            
            while attempt < max_attempts:
                # Calculate delay with exponential backoff
                if attempt < 24:  # First 2 minutes: 5 second polls
                    delay = base_delay
                elif attempt < 60:  # Next 3 minutes: 10 second polls
                    delay = 10
                else:  # After 5 minutes: 15 second polls
                    delay = 15
                    
                time.sleep(delay)
                attempt += 1
                
                # Show progress every minute
                if self.verbose and attempt % (60 // base_delay) == 0:
                    elapsed_mins = (attempt * base_delay) // 60
                    logger.info(f"⏳ Still waiting... {elapsed_mins} min elapsed (attempt {attempt}/{max_attempts})")
                
                try:
                    # fal.ai status endpoint requires Authorization header
                    status_response = requests.get(status_url, headers=status_headers, timeout=30)
                    
                    # Handle different HTTP status codes
                    if status_response.status_code == 404:
                        logger.error(f"✗ Job not found (404) - request may have expired")
                        return None
                    elif status_response.status_code == 429:
                        if self.verbose:
                            logger.warning("⚠ Rate limited - waiting longer before retry")
                        time.sleep(30)
                        continue
                    elif status_response.status_code == 503:
                        if self.verbose:
                            logger.warning("⚠ Service unavailable - fal.ai may be overloaded")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"✗ Too many service errors ({consecutive_errors}) - giving up")
                            return None
                        time.sleep(10)
                        continue
                    elif status_response.status_code not in [200, 202]:
                        if self.verbose:
                            logger.warning(f"⚠ Unexpected status code: {status_response.status_code}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"✗ Too many errors ({consecutive_errors}) - giving up")
                            return None
                        continue
                    
                    # Reset error counter on success
                    consecutive_errors = 0
                    
                    status_result = status_response.json()
                    status = status_result.get('status')
                    
                    # Log queue position if available
                    queue_position = status_result.get('queue_position')
                    if queue_position and self.verbose and attempt % 6 == 0:
                        logger.info(f"📊 Queue position: {queue_position}")
                    
                    if status == 'IN_QUEUE':
                        if self.verbose and attempt % 12 == 0:
                            logger.info("⏳ Job is in queue, waiting...")
                        continue
                    
                    elif status == 'IN_PROGRESS':
                        if self.verbose and attempt % 12 == 0:
                            logger.info("🎬 Video is being generated...")
                        continue
                    
                    elif status == 'COMPLETED':
                        # Debug: log the full response to see structure
                        if self.verbose:
                            logger.info(f"DEBUG - Full response keys: {list(status_result.keys())}")
                            logger.info(f"DEBUG - Full response: {status_result}")
                        
                        # Try multiple possible response structures
                        video_url = None
                        
                        # Structure 1: output.video.url
                        if 'output' in status_result:
                            video_url = status_result.get('output', {}).get('video', {}).get('url')
                        
                        # Structure 2: video.url
                        if not video_url and 'video' in status_result:
                            video_url = status_result.get('video', {}).get('url')
                        
                        # Structure 3: data.video.url
                        if not video_url and 'data' in status_result:
                            video_url = status_result.get('data', {}).get('video', {}).get('url')
                        
                        # Structure 4: response_url might contain the result
                        if not video_url and 'response_url' in status_result:
                            response_url = status_result.get('response_url')
                            if self.verbose:
                                logger.info(f"Fetching result from response_url: {response_url}")
                            try:
                                result_response = requests.get(response_url, headers=status_headers, timeout=30)
                                if result_response.status_code == 200:
                                    result_data = result_response.json()
                                    if self.verbose:
                                        logger.info(f"DEBUG - Result data: {result_data}")
                                    video_url = result_data.get('video', {}).get('url')
                            except Exception as e:
                                if self.verbose:
                                    logger.warning(f"Failed to fetch from response_url: {e}")
                        
                        if not video_url:
                            logger.error("✗ No video URL in response")
                            return None
                        
                        if self.verbose:
                            logger.info(f"✓ Video ready: {video_url}")
                        
                        # Download video with retry logic
                        max_download_retries = 3
                        for download_attempt in range(max_download_retries):
                            try:
                                video_response = requests.get(video_url, timeout=120)
                                if video_response.status_code != 200:
                                    if download_attempt < max_download_retries - 1:
                                        logger.warning(f"⚠ Download failed (attempt {download_attempt + 1}/{max_download_retries})")
                                        time.sleep(5)
                                        continue
                                    else:
                                        logger.error(f"✗ Failed to download after {max_download_retries} attempts: {video_response.status_code}")
                                        return None
                                
                                # Save video
                                char_name = Path(character_image_path).stem
                                output_path = Path(actual_output_folder) / f"{char_name}_kling.mp4"
                                
                                with open(output_path, 'wb') as f:
                                    f.write(video_response.content)
                                
                                if self.verbose:
                                    logger.info(f"✓ Video saved: {output_path}")
                                    file_size = output_path.stat().st_size / (1024 * 1024)
                                    logger.info(f"✓ File size: {file_size:.2f} MB")
                                    total_time = attempt * base_delay
                                    logger.info(f"✓ Total generation time: {total_time // 60}m {total_time % 60}s")
                                
                                return str(output_path)
                            
                            except Exception as download_error:
                                if download_attempt < max_download_retries - 1:
                                    logger.warning(f"⚠ Download error: {download_error} (retry {download_attempt + 1}/{max_download_retries})")
                                    time.sleep(5)
                                else:
                                    logger.error(f"✗ Download failed after {max_download_retries} attempts: {download_error}")
                                    return None
                    
                    elif status in ['FAILED', 'ERROR']:
                        error_msg = status_result.get('error', 'Unknown error')
                        logger.error(f"✗ Generation failed: {error_msg}")
                        
                        # Check if it's a retriable error
                        if 'quota' in error_msg.lower() or 'credit' in error_msg.lower():
                            logger.error("💳 Insufficient credits - please add more credits to your fal.ai account")
                        elif 'timeout' in error_msg.lower():
                            logger.error("⏱️ Server timeout - fal.ai may be overloaded, try again later")
                        
                        return None
                    
                    elif status == 'CANCELLED':
                        logger.error("✗ Job was cancelled")
                        return None
                        
                except requests.exceptions.Timeout:
                    if self.verbose:
                        logger.warning(f"⚠ Request timeout (attempt {attempt})")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"✗ Too many timeouts - giving up")
                        return None
                    continue
                    
                except requests.exceptions.ConnectionError:
                    if self.verbose:
                        logger.warning(f"⚠ Connection error - retrying")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"✗ Too many connection errors - giving up")
                        return None
                    time.sleep(10)
                    continue
                    
                except Exception as e:
                    if self.verbose and attempt % 12 == 0:
                        logger.warning(f"⚠ Status check error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"✗ Too many errors - giving up")
                        return None
                    continue
            
            # Timeout reached
            logger.error(f"✗ Timeout after {max_attempts * base_delay // 60} minutes")
            logger.error("💡 Possible causes:")
            logger.error("   - fal.ai servers are overloaded (try again during off-peak hours)")
            logger.error("   - Job stuck in queue (check fal.ai dashboard)")
            logger.error("   - Network connectivity issues")
            return None
            
        except Exception as e:
            logger.error(f"✗ Error: {str(e)}")
            return None
    
    def process_all_images_concurrent(self, target_directory: str, output_directory: str = None,
                                     max_workers: int = 5, custom_prompt: str = None,
                                     progress_callback=None, use_source_folder: bool = False):
        """Process all GenX images concurrently

        Args:
            target_directory: Input directory or file path
            output_directory: Fallback output directory (used when use_source_folder=False)
            max_workers: Maximum concurrent workers
            custom_prompt: Custom generation prompt
            progress_callback: Progress callback function
            use_source_folder: If True, save each video alongside its source image
        """
        if output_directory is None:
            output_directory = self.downloads_folder

        if self.verbose:
            logger.info(f"Scanning: {target_directory}")
            logger.info(f"Max workers: {max_workers}")
            if use_source_folder:
                logger.info("Output mode: Videos saved alongside source images")
            else:
                logger.info(f"Output folder: {output_directory}")

        # Collect all images
        all_images = []

        target_path = Path(target_directory)
        if target_path.is_file():
            # Single file mode - check for duplicate in appropriate location
            if use_source_folder:
                check_folder = str(target_path.parent)
            else:
                check_folder = output_directory
            if not self.check_duplicate_exists(str(target_path), check_folder):
                all_images.append(str(target_path))
            elif self.verbose:
                logger.info(f"Skipping duplicate: {target_path.name}")
        else:
            # Root directory
            genx_images = self.get_genx_image_files(target_directory, use_source_folder, output_directory)
            all_images.extend(genx_images)

            # Subdirectories
            try:
                for folder_path in Path(target_directory).iterdir():
                    if folder_path.is_dir():
                        genx_images = self.get_genx_image_files(str(folder_path), use_source_folder, output_directory)
                        all_images.extend(genx_images)
            except Exception as e:
                if self.verbose:
                    logger.error(f"Error: {e}")
        
        total_images = len(all_images)
        if total_images == 0:
            if self.verbose:
                logger.info("No GenX images found")
            return
        
        if self.verbose:
            logger.info(f"Found {total_images} GenX images")
            logger.info("Starting concurrent processing...")
        
        videos_created = 0
        videos_skipped = 0
        lock = threading.Lock()
        
        def process_image(image_path):
            nonlocal videos_created, videos_skipped
            
            image_name = Path(image_path).name
            
            if progress_callback:
                with lock:
                    progress_callback(videos_created + videos_skipped, total_images, f"Generating: {image_name}")
            
            try:
                result = self.create_kling_generation(image_path, output_directory, custom_prompt, use_source_folder)

                with lock:
                    if result:
                        videos_created += 1
                        if progress_callback:
                            progress_callback(videos_created + videos_skipped, total_images, f"Completed: {image_name}")
                    else:
                        videos_skipped += 1
                        if progress_callback:
                            progress_callback(videos_created + videos_skipped, total_images, f"Failed: {image_name}")
                
                return result
            except Exception as e:
                with lock:
                    videos_skipped += 1
                    if self.verbose:
                        logger.error(f"Error processing {image_name}: {e}")
                    if progress_callback:
                        progress_callback(videos_created + videos_skipped, total_images, f"Failed: {image_name}")
                return None
        
        # Process concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_image, img): img for img in all_images}
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    if self.verbose:
                        logger.error(f"Unexpected error: {e}")
        
        # Summary
        if self.verbose:
            logger.info("\n" + "=" * 80)
            logger.info("PROCESSING COMPLETE")
            logger.info(f"Videos created: {videos_created}")
            logger.info(f"Videos skipped: {videos_skipped}")
            logger.info(f"Total processed: {videos_created + videos_skipped}")
            logger.info("=" * 80)
