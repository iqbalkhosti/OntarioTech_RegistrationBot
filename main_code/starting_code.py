#!/usr/bin/env python3
"""
Ontario Tech Course Registration Bot
Quick setup for automated course registration assistance
"""

import json
import time
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import requests
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Course:
    code: str
    name: str
    credits: int
    available_spots: int
    total_spots: int
    instructor: str
    schedule: str
    prerequisites: str
    status: str  # "Open", "Closed", "Waitlist"

class OntarioTechBot:
    def __init__(self):
        self.driver = None
        self.db_path = "courses.db"
        self.setup_database()
        
    def setup_database(self):
        """Initialize SQLite database for course data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                name TEXT,
                credits INTEGER,
                available_spots INTEGER,
                total_spots INTEGER,
                instructor TEXT,
                schedule TEXT,
                prerequisites TEXT,
                status TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT,
                priority INTEGER,
                auto_register BOOLEAN DEFAULT 0,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def setup_driver(self, headless=True):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def login_to_platform(self, username: str, password: str, url: str = None):
        """Login to MyOntarioTech platform"""
        try:
            # Use provided URL or ask user for the correct URL
            if url:
                login_url = url
            else:
                login_url = input("Enter the MyOntarioTech login URL (or press Enter for default): ").strip()
                if not login_url:
                    login_url = "https://my.ontariotechu.ca"  # Updated URL
            
            print(f"🌐 Navigating to: {login_url}")
            self.driver.get(login_url)
            
            # Wait for login form
            wait = WebDriverWait(self.driver, 10)
            username_field = wait.until(EC.presence_of_element_located((By.ID, "userNameInput")))
            password_field = self.driver.find_element(By.ID, "passwordInput")
            
            username_field.send_keys(username)
            password_field.send_keys(password)
            
            # Click login button
            login_button = self.driver.find_element(By.ID, "submitButton")
            login_button.click()
            
            # Wait for dashboard to load (might need to adjust this selector)
            wait.until(EC.url_contains("myontariotech.ca"))
            print("✅ Login successful!")
            return True
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False
    
    def select_term(self, term="Winter 2026"):
        """Select the registration term from dropdown"""
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # Find and click the Select2 dropdown trigger
            # Look for the main select2 container
            dropdown_trigger = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".select2-container")))
            dropdown_trigger.click()
            
            # Wait for dropdown to open
            time.sleep(1)
            
            # Search for the term in the dropdown
            search_input = self.driver.find_element(By.CSS_SELECTOR, ".select2-input")
            search_input.clear()
            search_input.send_keys(term)
            
            # Wait for results to load
            time.sleep(2)
            
            # Click on the matching result
            results = self.driver.find_elements(By.CSS_SELECTOR, ".select2-results .select2-result")
            for result in results:
                if term.lower() in result.text.lower():
                    result.click()
                    print(f"✅ Selected term: {term}")
                    return True
            
            print(f"❌ Term '{term}' not found in dropdown")
            return False
            
        except Exception as e:
            print(f"❌ Term selection failed: {e}")
            return False
    def navigate_to_course_search(self, term="Winter 2026"):
        """Navigate to course search/registration page and select term"""
        try:
            # First, select the term
            if not self.select_term(term):
                return False
            
            # Wait a bit for the page to update after term selection
            time.sleep(2)
            
            # Now look for course search or registration elements
            # Try multiple possible selectors since we don't know the exact structure yet
            wait = WebDriverWait(self.driver, 10)
            
            # Try to find course search/registration page elements
            possible_selectors = [
                "input[placeholder*='course']",
                "input[placeholder*='Course']",
                ".course-search",
                "#course-search",
                "input[name*='course']",
                ".search-input"
            ]
            
            course_search_element = None
            for selector in possible_selectors:
                try:
                    course_search_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except:
                    continue
            
            if course_search_element:
                print("✅ Found course search interface")
                return True
            else:
                print("⚠️ Course search interface not found, but term selected successfully")
                return True
            
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return False
    
    def scrape_course_data(self, term: str, subject: str = None):
        """Scrape course data from the platform"""
        courses = []
        
        try:
            # This is a template - you'll need to customize based on actual HTML structure
            course_rows = self.driver.find_elements(By.CSS_SELECTOR, ".course-row")
            
            for row in course_rows:
                try:
                    code = row.find_element(By.CSS_SELECTOR, ".course-code").text
                    name = row.find_element(By.CSS_SELECTOR, ".course-name").text
                    credits = int(row.find_element(By.CSS_SELECTOR, ".credits").text)
                    
                    # Parse availability
                    availability_text = row.find_element(By.CSS_SELECTOR, ".availability").text
                    available_spots, total_spots = self.parse_availability(availability_text)
                    
                    instructor = row.find_element(By.CSS_SELECTOR, ".instructor").text
                    schedule = row.find_element(By.CSS_SELECTOR, ".schedule").text
                    status = row.find_element(By.CSS_SELECTOR, ".status").text
                    
                    course = Course(
                        code=code,
                        name=name,
                        credits=credits,
                        available_spots=available_spots,
                        total_spots=total_spots,
                        instructor=instructor,
                        schedule=schedule,
                        prerequisites="",  # Will be filled by LLM later
                        status=status
                    )
                    
                    courses.append(course)
                    
                except Exception as e:
                    print(f"⚠️ Error parsing course row: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Error scraping courses: {e}")
            
        return courses
    
    def parse_availability(self, availability_text: str) -> tuple:
        """Parse availability text like '15/30' into (available, total)"""
        try:
            parts = availability_text.split("/")
            available = int(parts[0])
            total = int(parts[1])
            return available, total
        except:
            return 0, 0
    
    def save_courses_to_db(self, courses: List[Course]):
        """Save course data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for course in courses:
            cursor.execute('''
                INSERT OR REPLACE INTO courses 
                (code, name, credits, available_spots, total_spots, instructor, schedule, prerequisites, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                course.code, course.name, course.credits, course.available_spots,
                course.total_spots, course.instructor, course.schedule,
                course.prerequisites, course.status
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ Saved {len(courses)} courses to database")
    
    def get_watchlist_courses(self) -> List[str]:
        """Get courses from user's watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT course_code FROM user_watchlist ORDER BY priority")
        watchlist = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return watchlist
    
    def add_to_watchlist(self, course_code: str, priority: int = 1, auto_register: bool = False):
        """Add course to watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_watchlist (course_code, priority, auto_register)
            VALUES (?, ?, ?)
        ''', (course_code, priority, auto_register))
        
        conn.commit()
        conn.close()
        print(f"✅ Added {course_code} to watchlist")
    
    def check_course_availability(self, course_code: str) -> Optional[Course]:
        """Check if a specific course has availability"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM courses WHERE code = ?", (course_code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Course(
                code=row[1], name=row[2], credits=row[3], available_spots=row[4],
                total_spots=row[5], instructor=row[6], schedule=row[7],
                prerequisites=row[8], status=row[9]
            )
        return None
    
    def attempt_registration(self, course_code: str) -> bool:
        """Attempt to register for a course"""
        try:
            # Navigate to registration page
            register_button = self.driver.find_element(By.CSS_SELECTOR, f"[data-course-code='{course_code}'] .register-btn")
            register_button.click()
            
            # Wait for confirmation or error
            wait = WebDriverWait(self.driver, 10)
            try:
                success_message = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "success-message")))
                print(f"✅ Successfully registered for {course_code}")
                return True
            except:
                error_message = self.driver.find_element(By.CLASS_NAME, "error-message")
                print(f"❌ Registration failed for {course_code}: {error_message.text}")
                return False
                
        except Exception as e:
            print(f"❌ Registration attempt failed: {e}")
            return False
    
    def monitor_and_register(self, max_attempts: int = 100, delay: int = 30):
        """Monitor watchlist courses and auto-register when available"""
        attempt = 0
        
        while attempt < max_attempts:
            print(f"\n🔄 Monitoring attempt {attempt + 1}/{max_attempts}")
            
            # Refresh course data
            self.driver.refresh()
            courses = self.scrape_course_data(term="Winter 2025")  # Adjust term as needed
            self.save_courses_to_db(courses)
            
            # Check watchlist
            watchlist = self.get_watchlist_courses()
            
            for course_code in watchlist:
                course = self.check_course_availability(course_code)
                if course and course.available_spots > 0:
                    print(f"🎯 {course_code} is available! Attempting registration...")
                    if self.attempt_registration(course_code):
                        # Remove from watchlist after successful registration
                        self.remove_from_watchlist(course_code)
                
            attempt += 1
            if attempt < max_attempts:
                print(f"⏳ Waiting {delay} seconds before next check...")
                time.sleep(delay)
    
    def remove_from_watchlist(self, course_code: str):
        """Remove course from watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_watchlist WHERE course_code = ?", (course_code,))
        conn.commit()
        conn.close()
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()

def main():
    bot = OntarioTechBot()
    
    try:
        # Setup
        bot.setup_driver(headless=False)  # Set to True for headless mode
        
        # Login (you'll need to input your credentials)
        print("🔗 We need the correct MyOntarioTech URL first")
        print("Common URLs:")
        print("1. https://my.ontariotechu.ca")
        print("2. https://ssbprod.ontariotechu.ca") 
        print("3. https://ontariotechu.ca/myontariotech")
        print("4. Enter custom URL")
        
        choice = input("Select URL option (1-4) or enter custom URL: ").strip()
        
        if choice == "1":
            url = "https://my.ontariotechu.ca"
        elif choice == "2":
            url = "https://ssbprod.ontariotechu.ca"
        elif choice == "3":
            url = "https://ontariotechu.ca/myontariotech"
        elif choice == "4":
            url = input("Enter the full URL: ").strip()
        else:
            url = choice  # Assume they entered a URL directly
        
        username = input("Enter your MyOntarioTech username: ")
        password = input("Enter your password: ")
        
        if not bot.login_to_platform(username, password, url):
            print("❌ Login failed. Try with a different URL or check your credentials.")
            return
        
        # Navigate to course search and select term
        if not bot.navigate_to_course_search(term="Winter 2026"):
            return
        
        # Initial course data scraping
        print("🔍 Scraping course data...")
        courses = bot.scrape_course_data(term="Winter 2025")
        bot.save_courses_to_db(courses)
        
        # Interactive menu
        while True:
            print("\n" + "="*50)
            print("ONTARIO TECH COURSE REGISTRATION BOT")
            print("="*50)
            print("1. View available courses")
            print("2. Add course to watchlist")
            print("3. View watchlist")
            print("4. Start monitoring and auto-registration")
            print("5. Manual registration attempt")
            print("6. Refresh course data")
            print("7. Exit")
            
            choice = input("\nEnter your choice (1-7): ")
            
            if choice == "1":
                # Show available courses
                conn = sqlite3.connect(bot.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT code, name, available_spots, total_spots, status FROM courses WHERE available_spots > 0")
                courses = cursor.fetchall()
                conn.close()
                
                if courses:
                    print("\n📚 Available Courses:")
                    for course in courses:
                        print(f"  {course[0]}: {course[1]} ({course[2]}/{course[3]} spots) - {course[4]}")
                else:
                    print("❌ No courses currently available")
            
            elif choice == "2":
                course_code = input("Enter course code to add to watchlist: ").upper()
                priority = int(input("Enter priority (1-10, 1 being highest): ") or "1")
                bot.add_to_watchlist(course_code, priority)
            
            elif choice == "3":
                watchlist = bot.get_watchlist_courses()
                if watchlist:
                    print("\n👁️ Your Watchlist:")
                    for course_code in watchlist:
                        course = bot.check_course_availability(course_code)
                        if course:
                            status = "✅ AVAILABLE" if course.available_spots > 0 else "❌ FULL"
                            print(f"  {course_code}: {course.name} - {status}")
                else:
                    print("📝 Watchlist is empty")
            
            elif choice == "4":
                print("🚀 Starting monitoring and auto-registration...")
                bot.monitor_and_register()
            
            elif choice == "5":
                course_code = input("Enter course code to register for: ").upper()
                bot.attempt_registration(course_code)
            
            elif choice == "6":
                print("🔄 Refreshing course data...")
                courses = bot.scrape_course_data(term="Winter 2025")
                bot.save_courses_to_db(courses)
            
            elif choice == "7":
                break
            
            else:
                print("❌ Invalid choice. Please try again.")
    
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    finally:
        bot.cleanup()

if __name__ == "__main__":
    main()