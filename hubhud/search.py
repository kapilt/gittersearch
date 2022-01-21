import tantivy
import sqlalchemy as rdb

from . import gitter


def get_schema():
    schema_builder = tantivy.SchemaBuilder()
    schema_builder.add_date_field("sent", stored=True)
    schema_builder.add_text_field("author", stored=True)
    schema_builder.add_text_field("id", stored=True)
    schema_builder.add_text_field("body", stored=True)
    schema = schema_builder.build()
    return schema


def search(path, query_phrase, max_results=10):
    schema = get_schema()
    index = tantivy.Index(schema, path, reuse=True)

    searcher = index.searcher()
    query = index.parse_query(query_phrase, ["body", "author"])

    qresults = searcher.search(query, max_results).hits
    results = []

    for (score, addr) in qresults:
        results.append({"score": score, "addr": addr, "doc": searcher.doc(addr)})
    return results


def index(session, path):

    schema = get_schema()
    index = tantivy.Index(schema, path, reuse=True)
    writer = index.writer()

    count = 0
    results = session.execute(
        rdb.select(gitter.Message).order_by(rdb.desc(gitter.Message.sent))
    )

    for r in results.all():
        m = r[0]
        writer.add_document(
            tantivy.Document(id=[m.id], sent=[m.sent], author=[m.author], body=[m.text])
        )
        count += 1
    writer.commit()
    return count
