from bs4 import BeautifulSoup
import os
import shutil
import sys
import json
import time
import urllib.parse
import requests
import re
import argparse
import threading
import io
from PIL import Image

args = argparse.ArgumentParser()
args.description = 'Download and convert a whole webtoon series to html files.'
args.add_argument('command', help='Link(s) to webtoon comic(s) to download. (This should be the link to chapter list.) to download OR a command to run. Available commands: update-all (updates all comics in the library.)', nargs='+', type=str)
args.add_argument('-p', '--proxy', help='Proxy to use', type=str, default="")
args.add_argument('-r', '--max-retries', help='How many times to retry failed downloads. (Default: 10)', type=int, default=10)
args.add_argument('-t', '--threads', help='How many threads to use when downloading. (Default: 10)', type=int, default=10)
args.add_argument('-l', '--library', help='Directory to store downloaded comics in. (Default: ./library)', type=str, default="./library")
args = args.parse_args()

LIBRARY_DIR = os.path.realpath(args.library)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

if not os.path.exists(LIBRARY_DIR):
    os.mkdir(LIBRARY_DIR)

proxies = {}
if args.proxy:
    proxies = {'http': args.proxy, 'https': args.proxy}

def make_safe_filename_windows(filename):
    illegal_chars = r'<>:"/\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '')
    return filename

def downloadComic(link):
    print(f'Link: {link}')
    html = requests.get(link, proxies=proxies, timeout=5).text
    soup = BeautifulSoup(html, 'html.parser')
    info = soup.find(class_='info')
    title = info.find(class_='subj').encode_contents().decode('utf-8').replace('<br>', ' ').replace('<br/>', ' ').strip() # Fix for titles with newlines (<br>)
    genre = info.find(class_='genre').text.strip()
    summary = soup.find(class_='summary').text.strip()
    banner = soup.find(class_='thmb').find('img')['src'].split('?')[0]
    banner_background = None
    try:
        banner_background = soup.find(class_='detail_bg').get('style').split('url(')[1].split(')')[0].split('?')[0]
        if banner_background.startswith("'"):
            banner_background = banner_background[1:]
        if banner_background.endswith("'"):
            banner_background = banner_background[:-1]
    except:
        pass # No banner background
    thumbnail = soup.find('meta', property='og:image').get('content')
    views = None
    subscribers = None
    rating = None
    i = 0
    for x in soup.find(class_='grade_area').find_all('li'):
        i += 1
        if i == 1:
            views = x.find(class_='cnt').text.strip()
        elif i == 2:
            subscribers = x.find(class_='cnt').text.strip()
        elif i == 3:
            rating = x.find(class_='cnt').text.strip()
    try:
        author_url = info.find(class_='author')['href']
        author = info.find(class_='author').text.replace('author info', '').strip()
    except:
        author_url = None
        author = info.find(class_='author_area').text.replace('author info', '').strip()
    author = re.sub(r'\s{2,}', ' ', author) # remove double spaces
    chapter_page_count = 0
    chapter_page_count_total = len(soup.find(class_='paginate').find_all('a'))

    print(f'Title: {title}')
    print(f'Genre: {genre}')
    print(f'Author: {author}')

    os.makedirs(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}', exist_ok=True)

    if banner:
        r = requests.get(banner, headers={'Referer': link}, proxies=proxies, timeout=5)
        image = Image.open(io.BytesIO(r.content))
        image = image.convert('RGBA')
        image.save(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/banner.png', quality=90)
    if banner_background:
        r = requests.get(banner_background, headers={'Referer': link}, proxies=proxies, timeout=5)
        image = Image.open(io.BytesIO(r.content))
        image = image.convert('RGB')
        image.save(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/banner_background.jpg', quality=90)
    if thumbnail:
        r = requests.get(thumbnail, headers={'Referer': link}, proxies=proxies, timeout=5)
        image = Image.open(io.BytesIO(r.content))
        image = image.convert('RGB')
        image.save(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/thumbnail.jpg', quality=90)

    chapters = []
    while chapter_page_count < chapter_page_count_total:
        chapter_page_count += 1
        print(f'\rFetching chapters from page {chapter_page_count}/{chapter_page_count_total}', end='')
        html = requests.get(f'{link}&page={chapter_page_count}', proxies=proxies, timeout=5).text
        soup = BeautifulSoup(html, 'html.parser')
        for l in soup.find(class_='paginate').find_all('a'):
            i = re.sub(r'.*&page=', '', l['href'])
            if i == '#': # this is the page we are currently on
                continue
            i = int(i)
            if i > chapter_page_count_total: # if the current page number is higher than the total number of pages, update the total
                chapter_page_count_total = i
        for chapter in soup.find_all('li', class_='_episodeItem'):
            ctitle = chapter.find(class_='subj').text.strip()
            if ctitle.endswith('BGM'): # This happens if the chapter includes background music
                ctitle = ctitle[:-3].strip()
            chapters.append({
                'title': ctitle, 
                'link': chapter.find('a')['href'],
                'thumbnail': chapter.find('img')['src'].split('?')[0],
                'date': chapter.find(class_='date').text.strip(),
                'likes': chapter.find(class_='like_area').text.replace('like', '').strip(),
            })

    print('')

    print(f'Chapter count: {len(chapters)}')

    print('')
    
    chapters = list(reversed(chapters)) # reverse the list because webtoon lists the newest chapters first

    chapter_index = 0
    for chapter in chapters:
        chapter_index += 1
        if os.path.exists(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/{chapter_index}.html'):
            print(f'Chapter {chapter_index}: {chapter["title"]} already downloaded, skipping redownload...')
            print('')
        else:
            print(f'Downloading chapter {chapter_index}: {chapter["title"]}')
            os.makedirs(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/chapter_images/{chapter_index}', exist_ok=True)
            r = requests.get(chapter['thumbnail'], headers={'Referer': link}, proxies=proxies, timeout=5)
            image = Image.open(io.BytesIO(r.content))
            image = image.convert('RGB')
            image.save(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/chapter_images/{chapter_index}/thumbnail.jpg', quality=90)
            html = requests.get(chapter['link'], proxies=proxies, timeout=5).text
            soup = BeautifulSoup(html, 'html.parser')
            imglist = soup.find(id='_imageList').find_all('img')
            i = 0
            running = 0
            for img in imglist:
                i += 1
                print(f'\rDownloading image {i}/{len(imglist)}', end='')
                def get(url, index):
                    nonlocal running
                    try:
                        img = requests.get(url, headers={'Referer': link}, proxies=proxies, timeout=5).content
                        image = Image.open(io.BytesIO(img))
                        image = image.convert('RGB')
                        image.save(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/chapter_images/{chapter_index}/{index}.jpg', quality=90)
                        running -= 1
                    except Exception as e:
                        print(e, file=sys.stderr)
                        print('Retrying in 1 second...', file=sys.stderr)
                        time.sleep(1)
                        get(url, index)
                running += 1
                threading.Thread(target=get, args=(str(img['data-url']).split('?')[0], int(i))).start()
                while running >= args.threads:
                    time.sleep(0.01)
            while running > 0:
                time.sleep(0.01)
            print('\n')
        # Update the html anyways
        f = open(f'{SCRIPT_DIR}/htmls/chapter.html', 'r', encoding='utf-8')
        html = f.read()
        f.close()
        html = html.replace('{{title}}', f'{title} - Chapter {chapter_index}: {chapter["title"]}')
        html = html.replace('{{main_title}}', f'<a id="title-link" href="index.html">{title}</a> &#x2013; Chapter {chapter_index}: {chapter["title"]}')
        html = html.replace('{{author}}', author)
        html = html.replace('{{thumbnail}}', f'chapter_images/{chapter_index}/thumbnail.jpg')
        meta = chapter.copy()
        del meta['thumbnail']
        meta['chapter_number'] = chapter_index
        meta['comic_link'] = link
        meta['comic_title'] = title
        meta['comic_author'] = author
        meta['comic_genre'] = genre
        html = html.replace('{{metadata}}', json.dumps(meta))
        content = ''
        for i in range(1, len(os.listdir(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/chapter_images/{chapter_index}'))): # No need to add 1 to the length because of the thumbnail file
            content += f'<img src="chapter_images/{chapter_index}/{i}.jpg" class="img">\n'
        html = html.replace('{{content}}', content)
        if chapter_index > 1:
            html = html.replace('{{prev}}', f'<a href="{chapter_index-1}.html">&lt;&#x2013; Previous Chapter</a>')
        else:
            html = html.replace('{{prev}}', '')
        if chapter_index < len(chapters):
            html = html.replace('{{next}}', f'<a href="{chapter_index+1}.html">Next Chapter &#x2013;&gt;</a>')
        else:
            html = html.replace('{{next}}', '')
        f = open(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/{chapter_index}.html', 'w', encoding='utf-8')
        f.write(html)
        f.close()

    print('Writing title/chapter list page...')

    f = open(f'{SCRIPT_DIR}/htmls/title.html', 'r', encoding='utf-8')
    html = f.read()
    f.close()
    html = html.replace('{{title}}', title)
    html = html.replace('{{author}}', author)
    html = html.replace('{{metadata}}', json.dumps({
        'link': link,
        'title': title,
        'genre': genre,
        'author': author,
        'author_link': author_url,
        'summary': summary,
        'views': views,
        'subscribers': subscribers,
        'rating': rating,
        'chapters': len(chapters)
    }))
    html = html.replace('{{summary}}', summary)
    chapters_html = ''
    for i in range(1, len(chapters)+1):
        chapters_html += f'<div class="chapter" onclick="window.location.href=\'{i}.html\'" id="chapter-{i}"><img class="chapter-image" src="chapter_images/{i}/thumbnail.jpg"><a href="{i}.html" class="chapter-text"><p>Chapter {i}: {chapters[i-1]["title"]}</p><p class="gray">{chapters[i-1]["date"]}</p></a></div>\n'
    html = html.replace('{{chapters}}', chapters_html)
    f = open(f'{LIBRARY_DIR}/{make_safe_filename_windows(title)}/index.html', 'w', encoding='utf-8')
    f.write(html)
    f.close()

    print('Done!\n')

def makeTitlesList():
    titles = ''
    titles_meta = []
    i = 0
    for file in os.listdir(LIBRARY_DIR):
        if os.path.isdir(f'{LIBRARY_DIR}/{file}'):
            f = open(f'{LIBRARY_DIR}/{file}/index.html', 'r')
            html = BeautifulSoup(f.read(), 'html.parser')
            f.close()
            j = json.loads(html.find('script', id='metadata').contents[0])
            titles += f'<div class="title" onclick="window.location.href=\'{urllib.parse.quote(file)}/index.html\'" id="title-{i}"><img class="title-image" src="{urllib.parse.quote(file)}/thumbnail.jpg"><a href="{urllib.parse.quote(file)}/index.html" class="title-text"><p>{j["title"]}</p><p class="gray">{j["author"]}</p></a></div>\n'
            titles_meta.append({
                'title': j['title'],
                'author': j['author'],
                'genre': j['genre'],
                'chapters': j['chapters'],
                'id': i,
                'path': file
            })
            i = i + 1
    f = open(f'{SCRIPT_DIR}/htmls/titles.html', 'r', encoding='utf-8')
    html = f.read()
    f.close()
    html = html.replace('{{metadata}}', titles)
    html = html.replace('{{titles}}', titles)
    f = open(f'{LIBRARY_DIR}/index.html', 'w', encoding='utf-8')
    f.write(html)
    f.close()
    img = Image.open(f'{SCRIPT_DIR}/htmls/webtoons.png')
    img.save(f'{LIBRARY_DIR}/webtoons.png', quality=90)
    # Copy all files for PWA
    for f in os.listdir(f'{SCRIPT_DIR}/htmls/PWA'):
        if os.path.isfile(f'{SCRIPT_DIR}/htmls/PWA/{f}'):
            shutil.copy(f'{SCRIPT_DIR}/htmls/PWA/{f}', f'{LIBRARY_DIR}/{f}')

links = []
if args.command[0] == 'update-all':
    for file in os.listdir(LIBRARY_DIR):
        if os.path.isdir(f'{LIBRARY_DIR}/{file}'):
            f = open(f'{LIBRARY_DIR}/{file}/index.html', 'r')
            html = BeautifulSoup(f.read(), 'html.parser')
            f.close()
            j = json.loads(html.find('script', id='metadata').contents[0])
            links.append(j['link'])
else:
    for link in args.command:
        for l in link.split(','):
            links.append(l)
tries = 0
for link in links:
    if 'm.webtoons.com' in link:
        raise Exception('Mobile version of webtoon links are not supported!')
    def f():
        global tries
        try:
            downloadComic(re.sub(r'&page=.*', '', link))
        except Exception as e:
            tries += 1
            print('Failed to download comic.', file=sys.stderr)
            print(e, file=sys.stderr)
            if tries > args.max_retries:
                print('Retrys exhausted. (' + str(args.max_retries) + ')\n', file=sys.stderr)
                return
            print('Retrying in 5 seconds...', file=sys.stderr)
            time.sleep(5)
            f()
    f()
print('Updating title list...')
makeTitlesList()
print('Done!')