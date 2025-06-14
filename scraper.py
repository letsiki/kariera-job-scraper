from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import logging
from logging_setup import logging_setup
from time import perf_counter
from datetime import datetime
from selenium.common.exceptions import (
    TimeoutException,
    ElementNotInteractableException,
)
import time
from job_ad import JobAd
from typing import Set
from pydantic import ValidationError
import json

logger = logging.Logger(__name__)
date = datetime.strftime(datetime.now(), "%Y-%m-%d")
logging_setup(
    logger,
    mode="fc",
    filename=f"log/{date}.log",
    filemode="w",
)

RETRY_WAIT = 60  # baseline time to wait (in seconds)
MAX_RETRIES = 5  # times to retry

# Generator for exponential backoff retry intervals
retry_generator = (RETRY_WAIT * 2**i for i in range(MAX_RETRIES))


def scrape(debug=False, retries=0) -> Set[JobAd]:
    if retries > MAX_RETRIES:
        raise TimeoutException(
            f"Max retries ({MAX_RETRIES}) reached, exiting"
        )
    if retries != 0:
        time.sleep(next(retry_generator))

    start = perf_counter()

    # initialize scraping options
    options = Options()
    # set scraper to run in headless mode
    options.add_argument("--headless")
    # pass the location of the firefox browser
    # it does not get automatically located because
    # it is snap-installed
    # Either point at the ELF binary:
    options.binary_location = (
        "/snap/firefox/current/usr/lib/firefox/firefox"
    )
    # —or— point at the launcher stub:
    # options.binary_location = "/snap/firefox/current/firefox.launcher"

    url = "https://www.kariera.gr/en"
    results = set()
    # Keep track of ingested ads to reduce completion time and skip duplicate removal
    link_set = set()
    driver = webdriver.Firefox(options=options)
    driver.get(url)

    # Introduce  a wait driver to be used with interactable elements
    long_wait = WebDriverWait(driver, 15)
    # and a shorter wait for data fetching
    #  the reason  for the shorter wait is
    # the fact that some elements are intentionally
    # missing, and I dont want to waste 10 seconds on
    # each of them, It is a fine balance and as of now
    # I think 1sec works fine
    short_wait = WebDriverWait(driver, 0.5)

    # define a function to use with elements containing text data
    def _safe_find_text_elem(by, value):
        try:
            elem = short_wait.until(
                EC.presence_of_element_located((by, value))
            )
            text = elem.get_attribute("innerText") or ""
            return text.strip()
        except:
            logger.info("value not found")
            return None

    # Find Cookie Allow Button
    try:
        cookie_allow_btn = long_wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                )
            )
        )
    except TimeoutException as e:
        logger.error(f"{e}\nrestarting scraper")
        return scrape(debug=debug, retries=retries + 1)
    # Click Allow Button
    try:
        cookie_allow_btn.click()
    except ElementNotInteractableException as e:
        logger.error(f"{e}\nrestarting scraper")
        return scrape(debug=debug, retries=retries + 1)
    # Locate the main page Search button and click on it(move to the search page)
    search_page = long_wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "/html/body/div[2]/div/div[2]/div/main/section[1]/div[1]/div[1]/div[3]",
            )
        )
    )
    search_page.click()
    # Loop through all different searches
    for job_role in ("Data", "Python", "IT", "Software", "Developer"):
        # Locate search box, clear it, and send it  the search string
        try:
            search_box = long_wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="rc_select_2"]')
                )
            )
        except TimeoutException as e:
            logger.error(f"{e}\nrestarting scraper")
            return scrape(debug=debug, retries=retries + 1)
        search_box.clear()
        search_box.send_keys(job_role + Keys.RETURN)
        # Page-Looper
        while True:

            # Find all job ads in the current page
            try:
                ad_links = long_wait.until(
                    EC.visibility_of_all_elements_located(
                        (
                            By.CSS_SELECTOR,
                            ".h5.BaseJobCard_jobTitle__ehsas",
                        )
                    )
                )
            except TimeoutException as e:
                logger.error(f"{e}\nrestarting scraper")
                return scrape(debug=debug, retries=retries + 1)
            # get one job ad per page if debug mode is on
            if debug:
                ad_links = ad_links[:5]
            # Loop through all job ads in the current page
            for ad_link in ad_links:
                try:
                    ad_link = long_wait.until(
                        EC.element_to_be_clickable(ad_link)
                    )
                except TimeoutException as e:
                    logger.error(f"{e}restarting scraper")
                    return scrape(debug=debug, retries=retries + 1)
                ad_link_text = ad_link.get_property("href")
                # filter out existing links and sponsored links (they are duplicates)
                if (
                    ad_link_text in link_set
                    or "sponsored" in ad_link_text  # type: ignore
                ):
                    continue
                else:
                    link_set.add(ad_link_text)
                ad_link.click()

                logger.info(f"fetching {ad_link_text}")
                driver.switch_to.window(driver.window_handles[-1])
                # find mandatory element(use wait instead of wait2), may turn this into a function
                try:
                    role = long_wait.until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                ".h4.JobTitle_title__irhyN",
                            )
                        )
                    ).text.strip()
                except TimeoutException as e:
                    logger.error(f"{e}did not fetch role restarting")
                    return scrape(debug=debug, retries=retries + 1)

                company = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    ".h6.JobCompanyName_name__V9AaS ",
                )

                location = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    ".JobDetail_value__1yhn_.main-body-text",
                )
                date_posted = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    "div.JobDetail_detail___Th__:nth-child(2) > div:nth-child(2)",
                )

                min_experience = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    "div.JobDetail_detail___Th__:nth-child(3) > a:nth-child(2)",
                )

                employment_type = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    "div.JobDetail_detail___Th__:nth-child(4) > a:nth-child(2)",
                )
                category = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    ".JobDetails_singleDoubleColumn__NwW1V > div:nth-child(1) > a:nth-child(2)",
                )

                remote = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    ".JobDetails_singleDoubleColumn__NwW1V > div:nth-child(2) > a:nth-child(2)",
                )

                details = []
                try:
                    contents_prt = short_wait.until(
                        EC.visibility_of_element_located(
                            (
                                By.CLASS_NAME,
                                "HtmlRenderer_renderer__mr82C",
                            )
                        )
                    )
                except:
                    contents_prt = None
                if contents_prt:
                    for contents_chd in contents_prt.find_elements(
                        By.XPATH, ".//p | .//strong | .//li"
                    ):
                        if contents_chd.text.strip() != "":
                            details.append(contents_chd.text.strip())
                try:
                    tags = short_wait.until(
                        EC.visibility_of_all_elements_located(
                            (
                                By.CSS_SELECTOR,
                                '[class*="Label_label__Llv6_"]',
                            )
                        )
                    )
                    tags = [tag.text for tag in tags]
                except:
                    tags = []

                data_json = _safe_find_text_elem(
                    By.CSS_SELECTOR,
                    "script[type='application/ld+json']",
                )
                try:
                    data = json.loads(data_json)  # type: ignore
                except TypeError:
                    continue
                date_posted = datetime.fromisoformat(
                    data.get("datePosted")
                )

                driver.close()
                driver.switch_to.window(driver.window_handles[-1])
                job_ad_dict = {
                    "role": role,
                    "company": company,
                    "location": location,
                    "date_posted": date_posted,
                    "min_experience": min_experience,
                    "employment_type": employment_type,
                    "category": category,
                    "remote": remote,
                    "details": details,
                    "tags": tags,
                    "ad_link": ad_link_text,
                    "date_posted": date_posted,
                }
                try:
                    results.add(JobAd(**job_ad_dict))
                except ValidationError as e:
                    logger.exception(
                        f"Couldn't validate entry {ad_link}\n{e}"
                    )

            button = long_wait.until(
                EC.visibility_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".ant-pagination-next > button:nth-child(1)",
                    )
                )
            )
            if button.is_enabled():
                button.click()
            else:
                break
    driver.quit()

    logger.info(f"fetched {len(results)} job ads")
    logger.info(
        f"operation completed in {int((perf_counter() - start) // 60)}  minutes and {round((perf_counter() - start) % 60)} seconds ({retries} retries)."
    )

    return results
