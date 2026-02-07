import os
import re
import sys
import time
import logging
import html
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import requests
from datetime import datetime

# 在GitHub Actions或Docker环境中使用webdriver-manager
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _ensure_utf8_output():
    try:
        if sys.platform == 'win32':
            import ctypes
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleOutputCP(65001)
            except Exception:
                pass
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

_ensure_utf8_output()

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.checkin_urls = self._load_checkin_urls()
        
        if not self.email or not self.password:
            raise ValueError("邮箱和密码不能为空")
        
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        """设置Chrome驱动选项"""
        logger.info(f"Checking environment: GITHUB_ACTIONS={os.getenv('GITHUB_ACTIONS')}, RUNNING_IN_DOCKER={os.getenv('RUNNING_IN_DOCKER')}")
        
        chrome_options = Options()
        # 针对截图页面，改用 normal 策略确保 JS 渲染完成
        chrome_options.page_load_strategy = "normal" 
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        if os.getenv('GITHUB_ACTIONS') or os.getenv('RUNNING_IN_DOCKER'):
            logger.info("Running in headless mode (CI/Docker)")
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            try:
                system_chromedriver = os.getenv('CHROMEDRIVER_PATH')
                system_chrome_bin = os.getenv('CHROME_BIN')

                if system_chrome_bin:
                    logger.info(f"Setting Chrome binary location: {system_chrome_bin}")
                    chrome_options.binary_location = system_chrome_bin

                if system_chromedriver and os.path.exists(system_chromedriver):
                    logger.info(f"Using system chromedriver at {system_chromedriver}")
                    service = Service(system_chromedriver)
                else:
                    logger.info("Using webdriver-manager to download chromedriver...")
                    service = Service(ChromeDriverManager().install())
                
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info("ChromeDriver initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ChromeDriver: {e}")
                raise
        else:
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
        
        try:
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(30)
        except Exception:
            pass

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def _load_checkin_urls(self):
        urls = []
        raw_urls = os.getenv('LEAFLOW_CHECKIN_URLS', '').strip()
        raw_url = os.getenv('LEAFLOW_CHECKIN_URL', '').strip()

        if raw_urls:
            urls.extend([u.strip() for u in raw_urls.split(',') if u.strip()])
        if raw_url:
            urls.append(raw_url)

        if not urls:
            urls = ["https://checkin.leaflow.net"]

        deduped = []
        seen = set()
        for url in urls:
            if url not in seen:
                deduped.append(url)
                seen.add(url)
        return deduped

    def _switch_to_new_window(self, old_handles, timeout=10):
        end_time = time.time() + timeout
        while time.time() < end_time:
            handles = self.driver.window_handles
            if len(handles) > len(old_handles):
                new_handles = [h for h in handles if h not in old_handles]
                if new_handles:
                    self.driver.switch_to.window(new_handles[-1])
                    return True
            time.sleep(0.5)
        return False

    def _switch_to_iframe_with_keywords(self, keywords, timeout=10):
        end_time = time.time() + timeout
        while time.time() < end_time:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                matched = False
                try:
                    self.driver.switch_to.frame(iframe)
                    body_text = ""
                    try:
                        body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    except Exception:
                        pass
                    if any(keyword in body_text for keyword in keywords):
                        matched = True
                        return True
                except Exception:
                    pass
                finally:
                    if not matched:
                        self.driver.switch_to.default_content()
            time.sleep(0.5)
        return False

    def _click_element(self, element):
        try:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            except Exception:
                pass
            element.click()
            return True
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False

    def _js_click_by_text(self, texts, timeout=10):
        script = """
        const texts = arguments[0] || [];
        function isVisible(el) {
          if (!el || !el.getBoundingClientRect) return false;
          const rect = el.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) return false;
          const style = window.getComputedStyle(el);
          if (!style) return false;
          return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
        }
        function isClickable(el) {
          if (!el) return false;
          const tag = (el.tagName || '').toLowerCase();
          if (tag === 'button' || tag === 'a') return true;
          const role = el.getAttribute && el.getAttribute('role');
          if (role === 'button') return true;
          return false;
        }
        function iterNodes(root) {
          const out = [];
          const queue = [root];
          while (queue.length) {
            const node = queue.shift();
            if (!node) continue;
            if (node.nodeType === 1) { 
              out.push(node);
              if (node.shadowRoot) queue.push(node.shadowRoot);
              if (node.tagName && node.tagName.toLowerCase() === 'iframe') {
                try { if (node.contentDocument) queue.push(node.contentDocument); } catch (e) {}
              }
              if (node.children) { for (const child of node.children) queue.push(child); }
            } else if (node.nodeType === 11 || node.nodeType === 9) {
              if (node.children) { for (const child of node.children) queue.push(child); }
              if (node.body) queue.push(node.body);
            }
          }
          return out;
        }
        const nodes = iterNodes(document);
        for (const el of nodes) {
          if (!isVisible(el)) continue;
          const text = (el.innerText || el.textContent || '').trim();
          for (const t of texts) {
            if (text.includes(t)) {
              let target = el;
              while (target && target.tagName !== 'BUTTON' && target.tagName !== 'A' && target !== document.body) {
                 target = target.parentElement;
              }
              try { (target || el).click(); return true; } catch (e) {}
            }
          }
        }
        return false;
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                if self.driver.execute_script(script, texts):
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def open_checkin_from_workspaces(self):
        try:
            current_url = ""
            try: current_url = self.driver.current_url or ""
            except: current_url = ""

            if "https://leaflow.net/workspaces" not in current_url:
                self.safe_get("https://leaflow.net/workspaces", max_retries=2, wait_between=3)
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)

            click_selectors = [
                "//button[contains(., '签到试用')]",
                "//*[contains(text(), '签到试用')]",
                "//button[contains(., '签到')]"
            ]

            target_btn = None
            end_time = time.time() + 15
            while time.time() < end_time and not target_btn:
                for selector in click_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for element in elements:
                            if element.is_displayed():
                                target_btn = element
                                break
                        if target_btn: break
                    except: continue
                if not target_btn: time.sleep(0.5)

            if not target_btn:
                if self._js_click_by_text(["签到试用", "每日签到"], timeout=8):
                    target_btn = True

            if not target_btn: return False

            old_handles = set(self.driver.window_handles)
            if target_btn is not True:
                self._click_element(target_btn)

            if self._switch_to_new_window(old_handles, timeout=5):
                return True

            checkin_btn_keywords = ["立即签到", "签到"]
            if self._js_click_by_text(checkin_btn_keywords, timeout=5):
                return True
                
            return False
        except Exception as e:
            logger.warning(f"打开工作空间签到入口失败: {e}")
            return False

    def _stop_page_load(self):
        try: self.driver.execute_script("window.stop();")
        except: pass

    def _is_driver_timeout(self, message):
        if not message: return False
        return ("HTTPConnectionPool" in message or "Read timed out" in message)

    def restart_driver(self):
        try:
            if self.driver: self.driver.quit()
        except: pass
        self.driver = None
        self.setup_driver()

    def safe_get(self, url, max_retries=2, wait_between=3):
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                self.driver.get(url)
                return True
            except Exception as e:
                last_error = str(e)
                self._stop_page_load()
            if attempt < max_retries: time.sleep(wait_between)
        raise Exception(f"Failed to load page: {url}. Last error: {last_error}")

    def close_popup(self):
        try:
            time.sleep(3)
            actions = ActionChains(self.driver)
            actions.move_by_offset(10, 10).click().perform()
            return True
        except: return False
    
    def wait_for_element_clickable(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, value)))
    
    def wait_for_element_present(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((by, value)))
    
    def login(self):
        cookie_str = os.getenv('LEAFLOW_COOKIE')
        if cookie_str:
            try:
                logger.info("检测到 LEAFLOW_COOKIE，尝试通过 Cookie 登录...")
                self.driver.get("https://leaflow.net")
                time.sleep(2)
                for item in cookie_str.split(';'):
                    if '=' in item:
                        name, value = item.strip().split('=', 1)
                        self.driver.add_cookie({'name': name, 'value': value})
                self.driver.refresh()
                time.sleep(5)
                if "login" not in self.driver.current_url:
                    logger.info("Cookie 登录成功")
                    return True
            except Exception as e:
                logger.warning(f"Cookie 登录出错: {e}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"开始登录流程，第 {attempt + 1}/{max_retries} 次尝试...")
                self.driver.get("https://leaflow.net/login")
                WebDriverWait(self.driver, 40).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(5)
                self.close_popup()
                
                email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='text'], input[type='email']", 10)
                email_input.clear()
                email_input.send_keys(self.email)
                
                password_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='password']", 10)
                password_input.clear()
                password_input.send_keys(self.password)
                
                login_btn = self.wait_for_element_clickable(By.XPATH, "//button[contains(., '登录') or contains(., 'Login')]", 10)
                login_btn.click()
                
                WebDriverWait(self.driver, 40).until(lambda d: "login" not in d.current_url)
                return True
            except Exception as e:
                logger.warning(f"登录尝试失败: {e}")
                if attempt < max_retries - 1: self.driver.refresh(); time.sleep(5)
        return False
    
    def get_balance(self):
        try:
            logger.info("获取账号余额...")
            self.driver.get("https://leaflow.net/dashboard")
            time.sleep(3)
            # 增强余额匹配，支持截图中的结构
            balance_selectors = ["//div[contains(., '余额')]//span", "//*[contains(text(), '¥')]"]
            for selector in balance_selectors:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    text = el.text.strip()
                    if any(c.isdigit() for c in text): return text
            return "未知"
        except: return "未知"
    
    def wait_for_checkin_page_loaded(self, max_retries=3, wait_time=20):
        # 针对截图优化探测逻辑
        for attempt in range(max_retries):
            logger.info(f"等待签到页面加载 ({attempt + 1}/{max_retries})...")
            time.sleep(5)
            # 探测“立即签到”文字
            page_source = self.driver.page_source
            if "立即签到" in page_source or "已签到" in page_source:
                logger.info("页面核心元素已加载")
                return True
            time.sleep(wait_time - 5)
        return False
    
    def find_and_click_checkin_button(self):
        logger.info("正在执行精准点击流程...")
        try:
            # 1. 优先检查是否已签到
            if "已签到" in self.driver.page_source or "已完成" in self.driver.page_source:
                 # 再次精细确认
                 if self._js_click_by_text(["已签到", "今日已签到"], timeout=2):
                     return "already_checked_in"

            # 2. 物理+JS 混合定位点击（针对截图中的蓝色按钮）
            script = """
            const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
            const target = btns.find(b => b.innerText.includes('立即签到'));
            if (target) {
                target.scrollIntoView({block: 'center'});
                target.click();
                return true;
            }
            return false;
            """
            self.driver.save_screenshot("before_checkin_attempt.png")
            if self.driver.execute_script(script):
                logger.info("通过 JS 脚本成功点击立即签到按钮")
                time.sleep(3)
                # 检查奖励领取
                self._js_click_by_text(["领取", "确定", "我知道了", "收下"], timeout=5)
                return True

            # 3. 兜底：通用文本点击
            if self._js_click_by_text(["立即签到"], timeout=5):
                return True

            return False
        except Exception as e:
            logger.error(f"点击流程异常: {e}")
            return False
    
    def _get_balance_value(self):
        try:
            balance_str = self.get_balance()
            match = re.search(r'(\d+\.?\d*)', balance_str)
            if match: return float(match.group(1))
        except: pass
        return None

    def checkin(self):
        logger.info("开始签到流程...")
        start_balance = self._get_balance_value()
        
        # 方案1
        if self.open_checkin_from_workspaces():
            res = self.find_and_click_checkin_button()
            if res: return "今日已签到" if res == "already_checked_in" else self.get_checkin_result()

        # 方案2
        for url in self.checkin_urls:
            try:
                self.safe_get(url)
                if self.wait_for_checkin_page_loaded():
                    res = self.find_and_click_checkin_button()
                    if res: return "今日已签到" if res == "already_checked_in" else self.get_checkin_result()
            except: continue
        
        raise Exception("所有签到方案均失败")
    
    def get_checkin_result(self):
        time.sleep(2)
        # 从记录或弹窗提取
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'获得\s*(\d+\.?\d*)\s*元', page_text)
        if match: return f"签到成功！获得了 {match.group(1)} 元奖励！"
        return "签到成功！"
    
    def run(self):
        try:
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                return True, result, balance
            else: raise Exception("登录失败")
        except Exception as e:
            logger.error(f"执行出错: {e}")
            return False, str(e), "未知"
        finally:
            if self.driver: self.driver.quit()

class MultiAccountManager:
    def __init__(self, auto_load=True):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts() if auto_load else []
    
    def load_accounts(self):
        accounts = []
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            for pair in accounts_str.split(','):
                if ':' in pair:
                    e, p = pair.split(':', 1)
                    accounts.append({'email': e.strip(), 'password': p.strip()})
        if not accounts:
            e, p = os.getenv('LEAFLOW_EMAIL'), os.getenv('LEAFLOW_PASSWORD')
            if e and p: accounts.append({'email': e, 'password': p})
        return accounts
    
    def send_notification(self, results):
        if not self.telegram_bot_token or not self.telegram_chat_id: return
        try:
            success_count = sum(1 for _, s, _, _ in results if s)
            msg = f"🎁 Leaflow自动签到通知\n📊 成功: {success_count}/{len(results)}\n\n"
            for email, success, result, balance in results:
                status = "✅" if success else "❌"
                msg += f"账号：{email[:3]}***\n{status} {result}\n💰 余额：{balance}\n\n"
            requests.post(f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage", 
                         data={"chat_id": self.telegram_chat_id, "text": msg, "parse_mode": "HTML"})
        except Exception as e: logger.error(f"通知失败: {e}")
    
    def run_all(self):
        results = []
        for account in self.accounts:
            success, result, balance = LeaflowAutoCheckin(account['email'], account['password']).run()
            results.append((account['email'], success, result, balance))
            time.sleep(5)
        self.send_notification(results)
        return all(r[1] for r in results), results

def main():
    try:
        manager = MultiAccountManager()
        manager.run_all()
    except Exception as e:
        logger.error(f"脚本终止: {e}")

if __name__ == "__main__":
    main()
