from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from time import sleep
import logging
from logging_setup import logging_setup
import pandas as pd
from datetime import datetime
from time import perf_counter

date = datetime.strftime(datetime.now(), "%Y-%m-%d")

start = perf_counter()

logger = logging.Logger(__name__)
logging_setup(
    logger, mode="fc", filename=f"log/{date}.log", filemode="w"
)

options = Options()
options.add_argument("--headless")
# Either point at the ELF binary:
options.binary_location = (
    "/snap/firefox/current/usr/lib/firefox/firefox"
)
# —or— point at the launcher stub:
# options.binary_location = "/snap/firefox/current/firefox.launcher"

url = "https://www.kariera.gr/en"
results = []
# Keep track of ingested ads to reduce completion time and skip duplicate removal
link_set = set()
driver = webdriver.Firefox(options=options)
driver.get(url)
wait = WebDriverWait(driver, 30)
cookie_allow_btn = wait.until(
    EC.element_to_be_clickable(
        (
            By.CSS_SELECTOR,
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        )
    )
)
cookie_allow_btn.click()
search_page = wait.until(
    EC.element_to_be_clickable(
        (
            By.XPATH,
            "/html/body/div[2]/div/div[2]/div/main/section[1]/div[1]/div[1]/div[3]",
        )
    )
)
search_page.click()
for job_role in ("Data", "Python", "IT", "Software"):
    search_box = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//*[@id="rc_select_2"]'))
    )
    search_box.clear()
    search_box.send_keys(job_role + Keys.RETURN)
    while True:
        job_list = wait.until(
            EC.visibility_of_element_located(
                (By.CLASS_NAME, "Jobs_resultsContainer__xwjB_")
            )
        )
        job_listings = job_list.find_elements(
            By.CLASS_NAME, "BaseJobCard_jobTitleContainer__gfcyi"
        )
        for job_listing in job_listings:
            ad_link = job_listing.find_element(By.TAG_NAME, "a")
            ad_link_text = ad_link.get_property("href")
            if ad_link_text in link_set:
                continue
            else:
                link_set.add(ad_link_text)
            ad_link.click()
            logger.info(f"fetching {ad_link_text}")
            driver.switch_to.window(driver.window_handles[-1])
            basic_info = wait.until(
                EC.visibility_of_element_located(
                    (
                        By.XPATH,
                        "/html/body/div[1]/div/div[2]/div/main",
                    )
                )
            )
            role = basic_info.find_element(
                By.CSS_SELECTOR, ".h4.JobTitle_title__irhyN"
            ).text
            try:
                company = basic_info.find_element(
                    By.CSS_SELECTOR,
                    ".h6.JobCompanyName_name__V9AaS ",
                ).text
            except:
                company = None
            sleep(0.5)
            location = basic_info.find_element(
                By.CSS_SELECTOR,
                ".JobDetail_value__1yhn_.main-body-text",
            ).text
            date_posted = basic_info.find_element(
                By.CSS_SELECTOR,
                "div.JobDetail_detail___Th__:nth-child(2) > div:nth-child(2)",
            ).text
            try:
                min_experience = basic_info.find_element(
                    By.CSS_SELECTOR,
                    "div.JobDetail_detail___Th__:nth-child(3) > a:nth-child(2)",
                ).text
            except:
                min_experience = None
            employment_type = basic_info.find_element(
                By.CSS_SELECTOR,
                "div.JobDetail_detail___Th__:nth-child(4) > a:nth-child(2)",
            ).text
            category = basic_info.find_element(
                By.CSS_SELECTOR,
                ".JobDetails_singleDoubleColumn__NwW1V > div:nth-child(1) > a:nth-child(2)",
            ).text
            try:
                remote = basic_info.find_element(
                    By.CSS_SELECTOR,
                    ".JobDetails_singleDoubleColumn__NwW1V > div:nth-child(2) > a:nth-child(2)",
                ).text
            except:
                remote = None
            details = []
            contents_prt = driver.find_element(
                By.CLASS_NAME, "HtmlRenderer_renderer__mr82C"
            )
            for contents_chd in contents_prt.find_elements(
                By.XPATH, ".//p | .//strong | .//li"
            ):
                if contents_chd.text.strip() != "":
                    details.append(contents_chd.text.strip())
            try:
                tags = basic_info.find_elements(
                    By.CSS_SELECTOR,
                    '[class*="Label_label__Llv6_"]',
                )
                tags = [tag.text for tag in tags]
            except:
                tags = None

            driver.close()
            driver.switch_to.window(driver.window_handles[-1])
            results.append(
                {
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
                }
            )
        button = wait.until(
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


df = pd.DataFrame(results)


df.to_pickle(f"data/{date}-df.pkl")
df.to_csv(f"data/{date}.csv", index=False)

logger.info(f"fetched {len(df)} job ads")
logger.info(
    f"operation completed in {int((perf_counter() - start) // 60)}  minutes and {round((perf_counter() - start) % 60)} seconds"
)
