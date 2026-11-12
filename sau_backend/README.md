## Starting the project
Python version: 3.10
1. Install the dependencies
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
2. Delete database.db in the db directory (if it does not exist, just run createTable.py), then run createTable.py to rebuild the database, so no dirty data is left
3. Change LOCAL_CHROME_PATH at the bottom of conf.py to the path of your local Chrome browser
4. Run sau_backend.py in the repo root
5. The type field (platform id): 1 Xiaohongshu, 2 WeChat Channels, 3 Douyin, 4 Kuaishou
## API
1. /upload post
    Upload endpoint. On success it returns the file's unique id, which is used later to publish the video
2. /login, parameter id: user name, parameter type: platform id. Login flow: the frontend and backend open an SSE connection; the backend gets the QR image as base64 and returns it to the frontend; after the QR code is scanned the backend saves the account and returns 200; the frontend closes the connection and then calls /getValidAccounts to get all accounts that can be used
3. /getValidAccounts returns all cookies that are currently valid. It is slow, because it checks every cookie one by one. status 1 = valid, 0 = invalid cookie
4. /postVideo publishes videos, post with JSON parameters
    file_list      the unique file ids returned by /upload
    account_list   the filePath field returned by /getValidAccounts
    type           type field (platform id)
    title          video title
    tags           list of video tags, without #
    category       the original author says this marks original content: 0 means not original, anything else means original, but in testing the field had no effect
    enableTimer    whether scheduled publishing is on; off by default, pass True to turn it on. If it is on, the three fields below are required, otherwise leave them out
    videos_per_day how many videos to publish per day
    daily_times    the times of day to publish, a list of integers, the same length as the list above
    start_days     start day: 0 means scheduled publishing starts tomorrow, 1 means the day after tomorrow
    The three fields above are described as I understand them; I am not sure this is right, nor why the original author set it up this way
## Database
See the db directory under the current directory: the .py file is the creation script, the .db file is the SQLite database
## Files
cookiesFile folder: stores cookie files
myUtils folder: stores the project's own Python modules
videoFile folder: where uploaded files are stored
web folder: web routes
conf.py: global configuration; remember to change LOCAL_CHROME_PATH in it to the path of the browser on this machine