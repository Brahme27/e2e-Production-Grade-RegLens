[RegLens guide](../README.md) › Part 8: Answers you can check

# 8.3 Words as they are written

In the [last chapter](02-checking-receipts-and-saying-i-dont-know.md) we checked every answer's
receipts and taught RegLens to decline politely. One thing remains before Meera sees anything: how
the answer travels from the server to her screen. Waiting two seconds for a blank box to fill
feels slow. Watching the words appear as they are written feels fast, even when it takes the same
time. That's **streaming**.

## A news ticker, not a newspaper

A printed newspaper arrives all at once, when it's finished. A live news ticker shows each line as
soon as it's written, and you start reading straight away. Streaming makes an answer behave like
the ticker.

Browsers and servers talk using **HTTP**, the language of the web: the browser sends a request,
the server sends back a response. Normally the response is sent in one piece. **Server-Sent
Events**, or **SSE**, is a simple standard that keeps one response open and lets the server push a
series of small, labelled messages down it, one after another.

RegLens sends its messages in a fixed order:

```
meta     → a trace id for this question (Part 11)
sources  → the route, the "as of" date and the 8 paragraphs
delta    → "The Internal Ombudsman must "      ┐
delta    → "report at least every six months"  ├ many small pieces of text
delta    → "…[1]."                             ┘
final    → the full answer with citations and the verification result
done     → nothing more to come
```

Notice that the **sources arrive first**, before a single word of the answer. Meera sees which
paragraphs are being read (the 2023 direction, marked superseded, with its validity window) while
the answer is still being written. That's reassuring for a careful reader, and it makes the wait
feel purposeful.

Why SSE and not **WebSockets**, the other common way to push data to a browser? WebSockets are a
two-way channel, great for chat or games where both sides talk constantly. Our traffic only flows
one way, server to browser, and SSE does that over plain HTTP, with less to build and less to go
wrong.

## Three details that matter

**Holding back "NOT_FOUND".** Remember the rule that the model replies `NOT_FOUND` when the sources
don't answer the question. If we streamed every character immediately, Meera might see "NOT_F"
flash on screen before it turned into the polite "I could not find this" message. So if the first
characters *could* be the start of `NOT_FOUND`, RegLens holds them back until it knows. A test makes
sure an answer that genuinely starts with "NBFCs…" still keeps its first letter.

**Cached answers stream too.** When an answer comes from a cache rather than the model, RegLens
replays it in small pieces, exactly like a live one. The console therefore has only one way of
showing answers, which means fewer bugs.

**Nobody in between may hold the stream.** Between the server and the browser sit other programs,
such as the console's own server and, in the cloud, a load balancer. Some of them like to collect
a whole response before passing it on, which would turn our ticker back into a newspaper. So the
response carries headers that say "don't store this, don't buffer this", the console passes the
stream through untouched, and the cloud load balancer is set to keep quiet connections open for
two minutes.

## Meera's view

Put together, Meera types her question, picks 5 January 2025, and presses Ask. Within moments the
sources panel fills with paragraphs that were in force on her date. Then the answer types itself out,
sentence by sentence, each ending in a clickable marker. Finally the verification note appears,
green if every statement is supported. It's the same answer it would have been without streaming,
but it *feels* like a conversation rather than a form submission.

*Want the details? See `walkthrough/07-answers/04-streaming.md` and
`src/reglens/api/routes/ask.py`.*

So far: RegLens finds the right paragraphs, writes a cited answer, checks it, knows when to decline,
and streams the result word by word. But how do we *know* any of it works well? Next, we prove it
with numbers, starting with an exam paper and its answer key.

**Next →** [9.1 The golden set](../09-evaluation/01-the-golden-set.md)
