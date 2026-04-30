from chroma_service import add_doc, search

print("Adding documents...")

add_doc("AI is artificial intelligence", "1")
add_doc("Python is a programming language", "2")
add_doc("Siddhu is super hero at full stack AI engineer", "3")


print("Searching...")

result = search("who is Siddhu?")
print(result)