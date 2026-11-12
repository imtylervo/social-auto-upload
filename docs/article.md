# Article Files and Theme Rendering

The article body is passed in as a UTF-8 file. HTML, Markdown and plain-text TXT are supported. A long body stays in the file, and the command line only needs the path.

## Preparing Markdown rendering

Install Node.js 22 or later (which includes npm), then run this once in the Python environment where this project is installed:

```powershell
sau article setup
```

This command installs the rendering dependencies at the versions pinned by the project. Later local rendering does not need the network. If you only use HTML/TXT, you do not need to install Node.js.

## Converting and previewing

```powershell
# List the themes
sau article themes

# Convert Markdown to themed HTML
sau article render --content-file examples/article.md --theme grace --output output/article.html

# Convert only the article structure, without theme styles
sau article render --content-file examples/article.md --theme plain --output output/plain.html

# Generate a preview file from existing HTML; the original inline styles are kept
sau article render --content-file article.html --output output/preview.html
```

Open the output file in a browser to preview it. If the output file already exists, the command reports an error. Add `--overwrite` to overwrite it. The input source file can never be overwritten.

| Theme | Purpose |
| --- | --- |
| `default` | Default theme, classic headings and accent colors |
| `grace` | Rounded quotes, soft decoration |
| `simple` | Light decoration, clear whitespace |
| `modern` | Warm colors, rounded corners, relaxed line spacing |
| `plain` | Converts only structure such as headings, paragraphs and lists, and uses the target platform's native layout |

When Markdown omits `--theme`, `default` is used. HTML/TXT do not accept `--theme`, and no theme is applied again. The four colored themes are rendered with [baoyu-md](https://github.com/JimLiu/baoyu-skills/tree/main/packages/baoyu-md).

## Body and images

Markdown supports headings, bold, italic, quotes, lists, horizontal rules, links, code blocks, tables and local images. HTML supports the matching article elements and inline `style`. For example:

```html
<h2 style="color:#2563eb">Section title</h2>
<p style="line-height:1.8">Body text with <strong>key points</strong>.</p>
<img src="images/example.png" alt="Image caption">
```

Relative image paths start from the directory of the source file. After output to another directory, the output still refers to the source file's local images. So you can preview it on the same computer, and you can pass it in again as an article file. Local images are not embedded in the output file. When sharing or moving the output, provide the images as well.

Not supported at the moment: web images, `data:` images, `file:` URLs, external stylesheets, `<style>`, scripts, iframes, SVG, formulas and chart extensions. Export diagrams such as Mermaid and PlantUML to local images first. TXT generates one paragraph per line, and HTML characters in the file are shown as plain text.

## Publishing to a platform

The local render command only generates files. To publish, keep using the article command of the target platform, and prepare the body in a format that platform supports. A format the renderer supports is not necessarily supported by every platform.

Dayu can accept Markdown directly, render the theme first, and then import the HTML:

```powershell
# --source "无需标注" = "No label needed" (Dayu information-source option)
sau dayu upload-article --account creator --title "How to read the work data dashboard" --content-file examples/article.md --theme modern --source "无需标注" --cover-indices 1
```

You can also first generate the themed HTML with `sau article render`, and then give the output file to `--content-file`. Neither path switches to `plain`. When no theme is given, `default` is used.

Dayu automatically converts the themed HTML into a compatible layout. It keeps text color, background color and approximate font size, and the body can still be selected and copied. The server-side preview is checked before the publish is confirmed. Rounded corners, exact font sizes, fonts, spacing and borders may differ from the local preview. The local renderer still outputs the full themed HTML. Other platforms can use the same source file and render result, and connect it according to their own format requirements.

To get Dayu's native layout, specify `--theme plain` explicitly. Formats not yet connected, such as italics, code blocks and user-entered tables, fail with an error before upload. For other requirements, see [Dayu image post publishing](./dayu-article.md).
