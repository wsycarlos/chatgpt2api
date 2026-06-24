from __future__ import annotations

auth_base = "https://auth.openai.com"
platform_base = "https://platform.openai.com"
platform_oauth_audience = "https://api.openai.com/v1"
platform_oauth_client_id = "app_2SKx67EdpoN0G6j64rFvigXD"
platform_oauth_redirect_uri = "https://platform.openai.com/auth/callback"
platform_auth0_client = "eyJuYW1lIjoiYXV0aDAtc3BhLWpzIiwidmVyc2lvbiI6IjEuMjEuMCJ9"

user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

sec_ch_ua = '"Chromium";v="145", "Google Chrome";v="145", "Not/A)Brand";v="99"'

common_headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "origin": platform_base,
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": sec_ch_ua,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": user_agent,
}
