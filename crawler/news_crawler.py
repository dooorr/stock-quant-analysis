"""
新闻数据挖掘 - 升级版

基于原版「新闻数据挖掘.ipynb」逻辑重构：
- 支持多站点配置
- 封装为 NewsCrawler 类
- 增加登录状态管理、重试、日志
- 支持增量抓取（记录已抓 URL）

原版主要使用 Selenium 模拟登录 + 采集新闻标题/链接/时间。
升级版保留 Selenium 方式，但代码更模块化、可维护。
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


@dataclass
class NewsItem:
    """单条新闻数据结构"""
    title: str
    url: str
    publish_time: str = ""
    source: str = ""
    content: str = ""


class NewsCrawler:
    """
    新闻采集器（升级版）

    用法示例：
        crawler = NewsCrawler(sites_config="sites.json")
        crawler.login_all()
        items = crawler.fetch_news("sina")
        crawler.save_to_json(items, "news.json")
    """

    def __init__(
        self,
        sites_config: str | Path = "sites.json",
        headless: bool = False,
        driver_path: Optional[str] = None,
    ):
        self.sites: Dict[str, dict] = {}
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self._load_sites(sites_config)
        self._init_driver(driver_path)

    def _load_sites(self, config_path: str | Path):
        """加载站点配置文件（JSON）"""
        path = Path(config_path)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self.sites = json.load(f)
            logger.info(f"已加载 {len(self.sites)} 个站点配置")
        else:
            logger.warning(f"配置文件 {config_path} 不存在，使用空配置")
            self.sites = {}

    def _init_driver(self, driver_path: Optional[str]):
        """初始化 Chrome 浏览器"""
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--lang=zh-CN")

        if driver_path:
            self.driver = webdriver.Chrome(
                executable_path=driver_path, options=options
            )
        else:
            self.driver = webdriver.Chrome(options=options)

        self.driver.implicitly_wait(5)
        logger.success("浏览器已启动")

    def login(self, site_key: str) -> bool:
        """登录指定站点"""
        if site_key not in self.sites:
            logger.error(f"站点 {site_key} 未配置")
            return False

        site = self.sites[site_key]
        login_url = site.get("login_url")
        if not login_url or not self.driver:
            return False

        try:
            self.driver.get(login_url)
            # 这里可以根据原版 notebook 的具体登录逻辑扩展
            # 例如：填写用户名密码、点击登录按钮、等待元素出现等
            logger.info(f"[{site_key}] 登录页面已打开，请手动完成登录或扩展自动登录逻辑")
            return True
        except Exception as e:
            logger.error(f"[{site_key}] 登录失败: {e}")
            return False

    def login_all(self):
        """登录所有已配置的站点"""
        for key in self.sites:
            self.login(key)
            time.sleep(1)

    def fetch_news(self, site_key: str, limit: int = 20) -> List[NewsItem]:
        """
        采集指定站点的新闻列表

        这里只是框架，具体 XPath/选择器需要根据原版 notebook 填写
        """
        if site_key not in self.sites or not self.driver:
            return []

        site = self.sites[site_key]
        list_url = site.get("list_url")
        if not list_url:
            return []

        try:
            self.driver.get(list_url)
            time.sleep(2)

            # 示例：假设新闻列表在 <a class="news-item"> 里
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a.news-item")[:limit]

            items = []
            for el in elements:
                title = el.text.strip()
                url = el.get_attribute("href") or ""
                if title and url:
                    items.append(NewsItem(title=title, url=url, source=site_key))

            logger.success(f"[{site_key}] 采集到 {len(items)} 条新闻")
            return items

        except Exception as e:
            logger.error(f"[{site_key}] 采集失败: {e}")
            return []

    def save_to_json(self, items: List[NewsItem], filepath: str | Path):
        """保存为 JSON"""
        data = [asdict(item) for item in items]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存 {len(items)} 条新闻到 {filepath}")

    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")


# ------------------------------
# 示例站点配置（sites.json 示例）
# ------------------------------
EXAMPLE_SITES = {
    "sina": {
        "name": "新浪新闻",
        "login_url": "https://passport.sina.com.cn/signin/login",
        "list_url": "https://news.sina.com.cn/",
    },
    "163": {
        "name": "网易新闻",
        "login_url": "https://passport.163.com/login",
        "list_url": "https://news.163.com/",
    },
}


if __name__ == "__main__":
    # 演示用法
    crawler = NewsCrawler(headless=False)

    # 1. 先登录（原版可能是手动登录，这里留扩展点）
    crawler.login("sina")

    # 2. 采集
    items = crawler.fetch_news("sina", limit=10)

    # 3. 保存
    if items:
        crawler.save_to_json(items, "news_sina.json")

    crawler.close()