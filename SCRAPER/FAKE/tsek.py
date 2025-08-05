import time
import requests
import csv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re

base_url = "https://www.tsek.ph/category/fact-checks/"
csv_file_path = 'fake.csv'

driver = webdriver.Chrome()

with open(csv_file_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['label', 'article']) # Label is '0' 

    scraped_urls = set() 
    found_older_article = False 

    current_page_url = base_url
    page_number = 1

    while not found_older_article:
        print(f"Navigating to page: {current_page_url}")
        driver.get(current_page_url)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, 'main'))
            )
            time.sleep(3) 
        except TimeoutException:
            print(f"Timeout waiting for 'main' element on page {current_page_url}. Assuming no more content.")
            break
        except NoSuchElementException:
            print(f"Element 'main' not found on page {current_page_url}. Page structure might have changed.")
            break

        soup_base = BeautifulSoup(driver.page_source, 'html.parser')

        main_element = soup_base.find('main')
        if not main_element:
            print(f"Could not find 'main' element on page {current_page_url}. Exiting.")
            break

        articles = main_element.find_all('article')

        if not articles:
            print(f"No articles found within 'main' element on page {current_page_url}. Exiting.")
            break

        for article in articles:
            if found_older_article:
                break 

            try:
                anchor_tag = article.find('a', href=True)
                if not anchor_tag:
                    continue 

                article_link = anchor_tag['href']
                if article_link in scraped_urls:
                    continue 

                print(f"  Processing article link: {article_link}")

                entry_meta = article.find('footer', class_='entry-meta') 
                if not entry_meta:
                    entry_meta = article.find('div', class_='entry-meta') 

                article_year = None
                if entry_meta:
                    time_tag = entry_meta.find('time')
                    if time_tag and time_tag.get_text(strip=True):
                        full_date_text = time_tag.get_text(strip=True)
                        if len(full_date_text) >= 4:
                            article_year = full_date_text[-4:] 

                if article_year and (article_year in ['2021', '2022', '2023', '2024', '2025']):
                    response_article = requests.get(article_link, allow_redirects=True, timeout=10)
                    if response_article.status_code == 200:
                        soup_article = BeautifulSoup(response_article.text, 'html.parser')

                        alt_text_found = None
                        main_content_div_for_figure = soup_article.find('div', class_='main-content')
                        if main_content_div_for_figure:
                            first_figure_in_main_content = main_content_div_for_figure.find('figure') # Finds the first figure
                            if first_figure_in_main_content:
                                img_tag_in_figure = first_figure_in_main_content.find('img', alt=True, recursive=False)
                                if img_tag_in_figure:
                                    alt_text_found = img_tag_in_figure['alt'].strip().lower()

                        if alt_text_found:
                            print(f"  DEBUG: First figure > img alt text found: '{alt_text_found}' for {article_link}")
                            if 'accurate' in alt_text_found:
                                print(f"  Skipping article {article_link}: First figure > img alt text contains 'accurate'.")
                                continue 
                        else:
                            print(f"  DEBUG: No 'figure > img' with 'alt' text found within main-content for {article_link}.")

                        extracted_content = ""
                        main_content_div = soup_article.find('div', class_='main-content')

                        if main_content_div:
                            blockquote_tag = main_content_div.find('blockquote')
                            if blockquote_tag:
                                extracted_content = blockquote_tag.get_text(strip=True)
                                print("    Content: Blockquote found.")
                            else:
                                all_paragraphs = main_content_div.find_all('p')
                                processed_paragraphs_texts = []

                                first_p_tag = all_paragraphs[0] if all_paragraphs else None
                                if first_p_tag:
                                    strong_claim = first_p_tag.find('strong', string=re.compile(r'CLAIM', re.IGNORECASE))
                                    if strong_claim:
                                        paragraph_text = first_p_tag.get_text(strip=True)
                                        processed_text = re.sub(r'\bCLAIM\b', '', paragraph_text, flags=re.IGNORECASE).strip()
                                        processed_text = re.sub(r'rating\{\}', '', processed_text, flags=re.IGNORECASE).strip()
                                        processed_paragraphs_texts.append(processed_text)
                                        print("    Content: First P with 'CLAIM' found and processed.")
                                        for p_tag in all_paragraphs[1:]:
                                            processed_paragraphs_texts.append(p_tag.get_text(strip=True))
                                    else:
                                        for p_tag in all_paragraphs:
                                            processed_paragraphs_texts.append(p_tag.get_text(strip=True))
                                else:
                                    print("    Content: No paragraphs found in main-content.")
                                qualifying_quoted_paragraphs = []
                                for p_text in processed_paragraphs_texts:
                                    quoted_matches = re.findall(r'["“]([^"”]+)["”]', p_text)
                                    for quote_text in quoted_matches:
                                        word_count = len(quote_text.split())
                                        if word_count >= 5:
                                            qualifying_quoted_paragraphs.append(p_text)
                                            break 

                                if qualifying_quoted_paragraphs:
                                    extracted_content = ' '.join(qualifying_quoted_paragraphs)
                                    print(f"    Content: Found {len(qualifying_quoted_paragraphs)} qualifying quoted paragraphs (after processing first P if applicable).")
                                else:
                                    print("    Content: No blockquote or qualifying quoted text found. Skipping content extraction.")
                        else:
                            print(f"Could not find 'main-content' for article: {article_link}. Skipping content extraction.")

                        if extracted_content:
                            csv_writer.writerow(['0', extracted_content])
                            scraped_urls.add(article_link) 
                            print(f"  Scraped article {len(scraped_urls)} (Year: {article_year})")
                        else:
                            print(f"  No extractable content found for article: {article_link}")

                    else:
                        print(f"  Failed to retrieve article content. Status code: {response_article.status_code} for {article_link}")

                else:
                    # If the article year is 2020 or older, set flag to stop
                    print(f"  Skipping article {article_link}: Published year is {article_year if article_year else 'N/A'}. Stopping process as it's outside 2021-2025 range.")
                    found_older_article = True
                    break 

            except requests.exceptions.RequestException as req_err:
                print(f"  Request error for {article_link}: {req_err}")
            except Exception as e:
                print(f"  An error occurred while processing article link {article_link}: {e}")

        if found_older_article:
            break

        try:
            next_page_link = driver.find_element(By.CSS_SELECTOR, 'a.next.page-numbers')
            if next_page_link:
                current_page_url = next_page_link.get_attribute('href')
                page_number += 1
                print(f"Moving to next page: {current_page_url}")
            else:
                print("No 'next page' link found. Assuming end of pagination.")
                break # Exit if no next page link
        except NoSuchElementException:
            print("No 'next page' link element found. Assuming end of pagination.")
            break

print(f"Scraped {len(scraped_urls)} articles. Data saved to {csv_file_path}")
driver.quit() 