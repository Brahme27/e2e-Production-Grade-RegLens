[RegLens guide](../README.md) › Part 6: Making it searchable

# 6.2 Meaning and exact words

In the [last chapter](01-chunks-with-a-label-on-top.md) we cut the corpus into labelled chunks.
Computers can't compare paragraphs the way we do, by reading them. They compare numbers. So now
we turn every chunk into numbers, in two different ways, because each way is good at something the
other is bad at.

## Meaning as coordinates

An **embedding** is a list of numbers that captures what a piece of text *means*. Texts with
similar meanings get similar numbers, even when they share no words at all.

Think of a map. Every city has coordinates, and cities that are close on the map have similar
coordinates: Pune and Mumbai sit near each other, London is far away. An embedding model gives
every chunk "coordinates" in a space of meaning. "A cloud vendor failed" lands near "outsourced
cloud service provider disruption", even though the wording is different. A list of numbers like
this is called a **vector**, and because every position holds a number, it's a **dense** vector.

To search, we turn the question into a vector too, and look for the chunks whose vectors sit
closest to it. Our embedding model is **bge-small**, which turns any text into 384 numbers.

## Exact words still matter

Meaning-based search has a weak spot: exact labels. To an embedding model, "SS1/23" and "SS2/21"
look almost alike, and "PRIN 2A.4.1R" is a blur. A compliance analyst who types an exact reference
expects that exact paragraph.

So each chunk gets a second, older kind of vector from **BM25**, the classic keyword-scoring
method behind search engines for decades. It rewards chunks that contain the question's words,
especially *rare* words, and doesn't over-reward a word repeated twenty times. It's like the index
at the back of a book: no understanding, but it never misses an exact term. Because most positions
in this vector are zero (a chunk uses only a few of all possible words), it's called a **sparse**
vector.

| Kind | Good at | Bad at |
|---|---|---|
| Dense (bge-small) | Meaning: "cloud vendor" ≈ "cloud service provider" | Exact labels like "SS1/23" |
| Sparse (BM25) | Exact words and references | Synonyms and paraphrases |

Part 7 searches with both at once. For Meera's question, BM25 can latch onto the exact words
"Internal Ombudsman", while the dense vector can connect "rejects the Ombudsman's decision" with
text about overruling it.

## Small models, on purpose

The original plan named **BGE-M3**, a model that produces both kinds of vector at once and reads
many languages. But it has 568 million parameters (the adjustable numbers inside a model, roughly
its size), would take hours to process our corpus on a laptop processor, and would use about 3 GB
of memory. bge-small has 33 million parameters and, together with BM25, finishes in minutes.

Both run through **fastembed**, a library that runs small models in **ONNX** format: a portable
way of saving a trained model so it runs fast on an ordinary processor, without installing a heavy
deep-learning framework. Swapping to a bigger model later is one setting, and the measurements of
Part 9 would show whether it pays off.

> **A bump on the road:** the first timing test said bge-small processed **3 chunks a second**,
> which meant hours per index. We almost redesigned everything. The cause wasn't the model: a large
> download was running at the same time, and Windows was virus-scanning every new file. Measured
> again on a quiet machine: about **11 chunks a second** for bge-small and about **1,000 a second**
> for BM25. The lesson: benchmark on a quiet machine before redesigning anything.

## A notebook for vectors too

Turning text into vectors is the slowest step, so, like the LLM notebook from chapter 2.3, every
vector is saved, keyed by a fingerprint of the model and the exact text. Rebuild the index after
three documents change, and only their changed paragraphs are processed again.

> **Try it:** run `uv run poe index`. The first run takes about 25 minutes on a laptop, because it
> builds every index variant we'll compare in Part 9. Run it again: the log reports every vector as
> already cached, and it's much faster.

*Want the details? See `walkthrough/05-indexing/03-embeddings.md`,
`docs/adr/0004-cpu-sized-models.md` and `src/reglens/index/embed.py`.*

So far: every chunk has two vectors, one for meaning and one for exact words. Next, we need a place
to store them that can search millions of numbers in milliseconds, and respect our dates.

**Next →** [6.3 Qdrant, the searchable shelf](03-qdrant-the-searchable-shelf.md)
