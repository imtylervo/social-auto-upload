"""Convert the source into the structure Xueqiu was tested to accept; images keep their positions and local paths."""
from html import escape
from html.parser import HTMLParser

from utils.article_content import ArticleDocument
from utils.article_render import ARTICLE_MARKDOWN_EXTENSIONS, load_article


class XueqiuHTML(HTMLParser):
    """The platform filters CSS, unifies headings and flattens lists; visible list numbers are kept before import."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.lists = []
        self.changes = set()

    def handle_starttag(self, tag, attrs):
        """Convert only structures the existing safe parser accepts; unknown formats are a clear error, content is never dropped silently."""
        attrs = dict(attrs)
        if tag not in {"section", "div", "p", "br", "span", "strong", "b", "em", "i", "a", "img",
                       "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "figure", "figcaption"}:
            raise ValueError(f"<{tag}> has not been verified in the native Xueqiu editor; convert it to paragraphs or local images before uploading")
        if attrs.get("style"):
            self.changes.add("自定义样式使用雪球原生样式")
        if tag.startswith("h") and len(tag) == 2:
            if tag != "h4":
                self.changes.add("各级标题统一为雪球小标题")
            tag = "h4"
        elif tag in {"ul", "ol"}:
            self.changes.add("列表转换为带序号或圆点的段落")
            self.lists.append([tag, int(attrs.get("start", "1"))])
            tag = "div"
        elif tag == "li":
            if not self.lists:
                raise ValueError("List items must be inside ul or ol")
            kind, number = self.lists[-1]
            self.lists[-1][1] += 1
            self.parts.append(f'<div>{number}. ' if kind == "ol" else '<div>• ')
            return
        elif tag == "blockquote":
            self.changes.add("引用保留文字和段落，使用雪球原生段落样式")
            tag = "div"
        elif tag in {"section", "figure", "figcaption"}:
            tag = "div"
        # The source has already passed ArticleDocument validation; CSS/class are not imported into the editor, to avoid a false impression that styles are kept.
        keep = {key: value for key, value in attrs.items()
                if (tag == "a" and key == "href") or (tag == "img" and key in {"src", "alt"})}
        self.parts.append("<" + tag + "".join(f' {key}="{escape(value or "", quote=True)}"'
                                                for key, value in keep.items()) + ">")

    def handle_endtag(self, tag):
        """End tags use the same conversion as start tags, so no mismatched rich text is produced."""
        if tag in {"ul", "ol"}:
            self.lists.pop()
        if tag in {"section", "figure", "figcaption", "ul", "ol", "li", "blockquote"}:
            tag = "div"
        elif tag.startswith("h") and len(tag) == 2:
            tag = "h4"
        self.parts.append(f"</{tag}>")

    def handle_data(self, value):
        """Keep the original text and whitespace; special characters are escaped as HTML text."""
        self.parts.append(escape(value))


def load_xueqiu_article(path):
    """Reuse the repo's HTML/Markdown/TXT input and relative image paths; return the converted body to be checked."""
    original = load_article(path, "plain" if path.suffix.lower() in ARTICLE_MARKDOWN_EXTENSIONS else None)
    converted = XueqiuHTML()
    converted.feed(original.content_html)
    converted.close()
    document = ArticleDocument("".join(converted.parts), path.parent)
    document.source_format = original.source_format
    document.normalizations = sorted(converted.changes)
    return document
