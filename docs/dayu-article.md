# Dayu Image Post Publishing

Publish an article from a UTF-8 body file. Use `.html`, `.htm` or Markdown (`.md`, `.markdown`) for a formatted body, and `.txt` for plain text. The article content stays in the file and the CLI only takes the file path, which suits long articles, many paragraphs and mixed text and images. The body is limited to 20,000 characters. A longer body fails with an error before upload.

## Login

The account is shared with video publishing, so there is no need to log in again:

```powershell
sau dayu login --account creator --expected-name "Your Dayu account name"
sau dayu check --account creator
```

For installation, see the [CLI guide](./CLI.md). On Windows, if `sau` is not found, you can use `.\.venv\Scripts\sau.exe`.

## Publish an article

```powershell
# --title "如何阅读作品数据面板" = "How to read the work data dashboard"; --source "无需标注" = "No label needed"
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file "examples/dayu_article.html" --source "无需标注" --author "Your author name" --cover-indices 1
```

This command actually publishes. It returns success once the platform confirms the publish, without waiting for review. You can first use `--prepare-only` to upload the images and check the filled-in form. That mode saves a local screenshot and stops. It does not publish and does not produce a server-side preview, so you cannot judge the final theme effect from it.

| Required item | Option | Requirement |
| --- | --- | --- |
| Account | `--account` | Name of a logged-in local account |
| Article title | `--title` | 5–50 characters; English characters count as half a character, rounded up |
| Body file | `--content-file` | A UTF-8 HTML, Markdown or TXT file; at most 20,000 characters of body text |
| Information source | `--source` | 无需标注 (No label needed), AI生成 (AI-generated), 虚构演绎 (Fictional dramatization), 营销信息 (Marketing information), 转载 (Repost), 个人观点 (Personal opinion), 不适宜未成年人 (Not suitable for minors) |
| Original link | `--source-url` | Required when 转载 (Repost) is chosen. Provide an http/https link to the original |

The current image post page has no "category" or "tags" fields like the ones in video publishing, so those options are not needed.

## Scheduled publishing

Add `--schedule "YYYY-MM-DD HH:MM"` to the command above. It is interpreted as **Beijing time (Asia/Shanghai, UTC+8)**. The time must be between 2 hours and 7 days after the current time, and the minutes must be a multiple of 5, for example `10:30` or `10:35`. Leave time for image upload and body processing. The range is checked again when the form is filled in. An invalid time is not rounded automatically or changed to immediate publishing.

```powershell
# --title "如何阅读作品数据面板" = "How to read the work data dashboard"; --source "无需标注" = "No label needed"
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file examples/article.md --theme modern --source "无需标注" --cover-indices 1 --schedule "2027-01-01 10:30"
```

Replace the example date with a time in the real allowed range. Without this option, the article is published immediately. After the platform confirms the original work and the scheduled time, the command returns that the schedule succeeded. It does not wait for the time to arrive or for review. If review takes longer, the platform may publish it later than the scheduled time.

## How to provide a formatted body

Express the article structure with HTML tags, for example:

```html
<h1>Section title</h1>
<p>A body paragraph, which can contain <strong>bold key points</strong>.</p>
<img src="images/example.png">
<blockquote>Quoted content.</blockquote>
<ol>
  <li>Step one.</li>
  <li>Step two.</li>
</ol>
<ul>
  <li>A list item.</li>
</ul>
<hr>
<p>The last paragraph.</p>
```

| Article format | How to write it |
| --- | --- |
| Paragraphs, line breaks | `<p>`, `<br>` |
| Section headings | `<h1>` to `<h6>` |
| Bold | `<strong>` or `<b>` |
| Quote | `<blockquote>` |
| Ordered and unordered lists | `<ol>`, `<ul>`, with `<li>` for each item |
| Horizontal rule | `<hr>` |
| Image | `<img src="local image path">` |

You can provide the HTML fragment above directly, or a complete HTML file with `html/head/body`. Tags must be closed correctly, except empty tags such as images and line breaks.

The current command supports the formats in the table above, plus themed HTML with inline CSS and the `section/div/span/figure` layout containers. A styled body is automatically converted to **Dayu-compatible layout**. Text color, background color and approximate font size are kept, and the body is still selectable and copyable text. Rounded corners cannot be kept. Fonts, spacing and borders may differ from the local preview. Not every CSS rule is guaranteed to display as written. Before the publish is confirmed, the full body, the order of text and images, the text colors and the background colors in the server-side preview are checked. If the check fails, publishing is aborted.

Keep the original Markdown/HTML file. When the Dayu web editor imports the compatible layout again, it may clean up colors, layout or images. The effect after re-editing on the web is outside what this command preserves. The editor screenshot from `--prepare-only` also does not represent the final theme effect.

Italics, code blocks, user-entered tables, external stylesheets, scripts and other tags that are not connected yet are reported before upload so you can change them. Word files are not connected yet.

Markdown is first rendered to HTML locally and then imported into Dayu. The default theme is `default`. The options are `default/grace/simple/modern/plain`, and `plain` converts only the structure. Before using Markdown for the first time, run `sau article setup`, which needs Node.js 22+. For preview and conversion, see [Article Files and Theme Rendering](./article.md).

```powershell
# --title "如何阅读作品数据面板" = "How to read the work data dashboard"; --source "无需标注" = "No label needed"
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file examples/article.md --theme modern --source "无需标注" --cover-indices 1

# Generate the themed HTML first, then publish that same HTML; do not pass --theme for HTML input
sau article render --content-file examples/article.md --theme modern --output output/article.html
sau dayu upload-article --account creator --title "如何阅读作品数据面板" --content-file output/article.html --source "无需标注" --cover-indices 1
```

For a complete example, see [dayu_article.html](../examples/dayu_article.html). A plain-text file generates one paragraph per line, and HTML characters in it are not treated as formatting.

## Images and covers

Images in the body use local paths. A relative path starts from the **directory of the body file**. Absolute paths also work. The program uploads images at their positions in the article and keeps the order of text and images.

Each image can be at most 5 MB and must decode normally on the local machine. Web image URLs, `data:` images and `file:` URLs are not supported yet, so prepare local images first. You can pass HTML with inline image styles, but images are inserted through the platform uploader and use the platform's default image layout. The CSS or size of the original image is not kept.

A landscape cover can be chosen from the body images. The index counts from 1 in the order the images appear in the body:

```powershell
# Single cover: use the 1st body image
--cover-indices 1

# Three covers: use the 1st, 3rd and 2nd body images, in that order
--cover-indices 1 3 2
```

Three covers need 3 different body image indices. The program generates the covers with the page's default crop box. When `--cover-indices` is omitted, the page's cover setting is kept.

## Other features on the page

The table below follows the current image post publishing page. Some features may depend on account permissions.

| Page feature | Support in the current command |
| --- | --- |
| Author name | Optional, with `--author`. At most 10 characters; English counts as half a character, rounded up. If omitted, the value on the web page is kept |
| Set as default author | Changing it is not supported yet |
| Single cover, three covers | Choosing from the body images is supported, with `--cover-indices` |
| Portrait cover | Not supported yet |
| Choose images from the personal asset library | Not supported yet. The command currently uses the local images referenced by the body file |
| Scheduled publishing | `--schedule` is supported; 2 hours to 7 days ahead in Beijing time, in 5-minute steps |
| Import document | The web page supports doc/docx/pdf/txt, at most 5 MB. Not connected yet. The command currently uses HTML/Markdown/TXT files |
| Insert video into the body | Not supported yet |
| Writing assistant: title, typo and rule-violating ad checks | Follows the site's settings. There is no option to configure it yet |
| Web preview | The publishing process goes into the preview and confirms it. There is no separate preview command |
| Save draft, clear | No corresponding command yet |

## Viewing the publish result

A successful publish returns the work ID, which means the platform has confirmed this publish. It does not wait for review or public access. Before submitting, the editor's body, image order and supported formats are checked. When there are theme styles, the compatible layout in the server-side preview is also checked.

If the publish result is not confirmed, for example because the network dropped, use the result file named in the log to query the original work read-only, to avoid publishing twice:

```powershell
sau dayu verify --account creator --result "cookies/dayu_results/this_result_file.json"
```

The query succeeds when it finds the submitted original work, and also succeeds if the work is still under review. For a scheduled work, it also checks the scheduled time in the result file, and succeeds once the schedule is confirmed. You can also query by work ID:

```powershell
sau dayu verify --account creator --type article --content-id "work ID"
```

To additionally check the public article, add `--public`:

```powershell
sau dayu verify --account creator --result "cookies/dayu_results/this_result_file.json" --public --timeout 900
```

The public check waits until the article can be accessed publicly, and checks the title, the account and that images load. With this publish's result file, it also compares the full body, the order of text and images, and the supported formats. For a themed article it also checks text color and background color. On success it returns the public article link. The public check is a separate operation and does not affect the success result already confirmed by the publish.

By default it waits up to 600 seconds for each image to upload. You can adjust this with `--upload-timeout`, in seconds. `--headed` shows Chrome, and `--debug` saves a screenshot on error.
