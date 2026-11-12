# Xueqiu Long Articles

Supports UTF-8 HTML, Markdown and TXT body files. Images are written at their positions in the source file. The program uploads local images and inserts them at those positions. It also supports a separate cover, public/private sharing and a creation declaration. The official CLI has been used to verify the HTML structure, images between paragraphs, the cover, real publishing, and querying the original work in the management backend.

## First-time setup

First follow the [project installation guide](./install.md) to install Python 3.10–3.12, the dependencies and the `sau` command, and copy `conf.example.py` to create a local `conf.py`. Xueqiu uses the installed Google Chrome. Installing Chromium is not the same as installing Chrome. If Chrome is not in its default location, set `LOCAL_CHROME_PATH` in `conf.py` to the real executable path on your machine. Left empty (the default), the system Chrome channel is used.

Markdown source files are recommended. Node.js 22+ is required. Run `sau article setup` the first time to install the rendering dependencies. The repository provides a [Markdown example](../examples/xueqiu_article.md) with two images between paragraphs. The image files ship with the repository. Run it from the project root:

```powershell
sau article setup
# --title "雪球文章示例" = "Xueqiu article example"
# --visibility 私人 = private
# --declaration "本文包含AI生成内容" = "This article contains AI-generated content"
sau xueqiu upload-article --account creator --title "雪球文章示例" --content-file examples/xueqiu_article.md --visibility 私人 --declaration "本文包含AI生成内容" --prepare-only
```

Log in first, as described in the next section. Prepare mode still saves a remote draft automatically. After you have checked the content, remove `--prepare-only` to actually publish.

An [HTML example](../examples/xueqiu_article.html) and TXT are also supported. Neither format needs Node.js.

## Log in once

```powershell
sau xueqiu login --account creator --expected-name "Your Xueqiu nickname"
sau xueqiu check --account creator
```

Complete the verification in the Chrome window that opens. The program saves a local session and binds it to the user ID, so the same alias does not overwrite another account. The account and password do not need to go into commands or source code. Later uploads and queries reuse this session.

A visible Chrome is used by default. Local headless access has been blocked by the platform before. You can pass `--headless` explicitly, but do not treat an access block as an expired login.

## Source files and images

Markdown example. Image paths are relative to the **directory of the source file**:

```markdown
# Part one

A paragraph before the image, with **bold** text.

![First image](images/first.png)

## Part two

This paragraph sits between the two images.

![Second image](images/second.jpg)

The ending after the second image.
```

HTML uses the same source order:

```html
<h1>Part one</h1>
<p>A paragraph before the image, with <strong>bold</strong> text.</p>
<img src="images/first.png">
<h2>Part two</h2>
<p>This paragraph sits between the two images.</p>
<img src="images/second.jpg">
<p>The ending after the second image.</p>
```

Markdown uses `# Title`, `## Subtitle`, `**bold**` and `![caption](images/figure.png)`. Using Markdown for the first time needs Node.js 22+. Run `sau article setup` in the repository to install the existing rendering dependencies. Images must be local GIF/JPEG/PNG files that exist and are not empty. Web image URLs and data URLs are not accepted.

Xueqiu uses its own native style. Headings of all levels become the platform's subheading. Paragraphs, bold, italic and links are kept. Lists become paragraphs that keep their numbers or bullets. Quotes keep their text and paragraphs. Custom CSS such as colors, fonts and spacing is not guaranteed to be kept. The result file lists the conversions that happened. Structures not yet verified, such as tables, code blocks and horizontal rules, fail with a clear error before a remote draft is created.

## Publishing

```powershell
# --declaration "本文包含AI生成内容" = "This article contains AI-generated content"
sau xueqiu upload-article --account creator --title "Article title" --content-file "article.md" --declaration "本文包含AI生成内容"
```

Without `--prepare-only`, the article is actually published. `--visibility` accepts `公开` (public) or `私人` (private). The default is public. For testing, or when only you should see it, pass `--visibility 私人` explicitly. `--declaration` must be chosen to match the real situation: `不添加创作声明` (do not add a creation declaration) or `本文包含AI生成内容` (this article contains AI-generated content).

A separate cover is optional: `--cover "cover.png"`. It uses the platform's default crop area. Body images are read only from the source file. There is no option to append images at the end of the article. The title must be a non-empty single line, and the body must contain text. Size and length limits follow the platform's validation.

To only check, add `--prepare-only`. Xueqiu saves a remote draft automatically while editing. This mode checks the preview and saves a screenshot. Running it repeatedly may create new drafts. If the page restores an existing article, the program refuses to overwrite it. `--debug` saves a screenshot on failure.

## Results and error lookup

A successful publish returns `status: published` and the work ID. The program checks the subject, title, sharing scope and body that the platform finally accepted, and looks the work up by ID in the published-management list. `management_verified: true` means the backend lookup of the original work also passed. A private article shows 仅自己可见 (visible only to me), which does not mean it was not published.

`prepared` only means the draft/preview check is done. The command prints the path of the result JSON. The result and screenshots are saved under `xueqiu_results` in the account directory.

If submission times out or returns `submission_unknown`, only query the original work. Do not upload again:

```powershell
sau xueqiu verify --account creator --result "this_result_file.json"
```

This command checks the backend against the original work ID, title, account and sharing scope in the result file. It also uses the source path recorded at publish time to re-check the body and images in the backend. Before querying, keep the source file and images and do not change their content. If the source file has changed, the command reports a clear error. For older successful results that did not record the source path, only the work identity and sharing scope are checked. This does not re-verify the body. If there is no ID, first check the backend by title and time. Do not simply rerun the publish. If the platform accepted the article but a later check reports an error, keep that ID and query it, to avoid duplicate works.

No scheduling setting was seen in the full long-article form of this account. Video, Word import, custom cover cropping, @-mentioning friends, topics and stock links are not supported yet.

## Development verification

After the project, Chrome and `sau article setup` are installed, you can run:

```powershell
python -m unittest tests.test_xueqiu_uploader tests.test_article_render tests.test_sau_browser_cli -v
```

These tests use temporary files, local browser pages and mocked query responses. They need no Xueqiu account and do not publish any article. Paginated queries have mock tests. Different systems and accounts still need to be verified in their own environments. The environment of the current real-publishing acceptance is Windows Chrome.
