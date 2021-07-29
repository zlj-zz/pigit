import urllib.request
import re
# import urllib2

base_url = "https://github.com/github/gitignore/blob/master/%s.gitignore"
name = "Python"

r = urllib.request.urlopen(base_url % name, timeout=1)
# r = urllib2.urlopen(base_url % name, timeout=1)
text= r.read().decode('utf-8')
# print(text)

text = re.findall(r"(<table.*?>.*?<\/table>)", text, re.S)

content_re = re.compile(r"<\/?\w+.*?>", re.S)
res = content_re.sub("", text[0])
print(res.encode())
res = re.sub(r"(\n[^\S\r\n]+)+", "\n", res)
print(res)
