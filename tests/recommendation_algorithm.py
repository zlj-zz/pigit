from collections import Counter

word = "cog"
fre = dict(Counter(word))
print(fre)


words = [
    "dog",
    "cat",
    "cow",
    "bear",
    "bird",
    "rabbit",
    "mouse",
    "tiger",
    "leopard",
    "dolphin",
    "elephant",
    "shark",
]

words = {word: dict(Counter(word)) for word in words}

similar = {
    w: [fre[ch] - words[w].get(ch, 0) for ch in word]
    + [words[w][ch] - fre.get(ch, 0) for ch in w]
    for w in words
}
print(similar)
print(similar.items())

res = min(similar.items(), key=lambda item: sum(map(lambda i: i ** 2, item[1])))
print(res)

raw_input("1:")









