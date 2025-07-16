# Webtoon to .epub converter
A program to download/archive down a whole webtoon comics into offline html files.<br>
Note: **!!This could break at any time because it relies on the current layout of Webtoon's website!!**

## Installation

Using a venv:
```sh
git clone https://github.com/westhecool/webtoon-to-html.git
cd webtoon-to-html
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Usage

```sh
./venv/bin/python3 main.py [link to chapter list of Webtoon series]
```
The input **must** be a link to the chapter list of the webtoon series. Please do not use the mobile version of the site as it's not tested.

## TODO

- [x] Working downloader
- [x] Web html reader
- [x] Chapter/title listing page
- [x] HTML metadata
- [ ] More metadata
- [ ] Possibly better ui for the offline html files
- [ ] Figure out how to download background music from webtoons
- [x] Add functions to automatically/manually update new chapters to local library