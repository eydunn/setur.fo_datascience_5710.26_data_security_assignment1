# Speaker notes

Read this beside the slides. Each section is one slide, and the numbered points are the points on that slide, in the same order. Say the point, then the sentence under it. The "If asked" line is only for a question.

Quote time and memory from the run you show. The published MD5 digest is a citation. Leave it as printed.

## Slide 1 — Title

**How Secure Is a Truncated SHA-2 Digest?**
We kept only the front of a SHA-256 digest and measured when a collision on that front becomes practical.

**Birthday collisions on a prefix, and a signature that checks only that prefix**
Two messages with the same leading bits pass one signature check. That is the whole talk.

**Kristmund, Eyðun, Torkil — Data Security**
Names only. Move on.

## Slide 2 — The question

**1. A verifier keeps the first n bits of SHA-256 and ignores the rest.**
The check is shorter than the digest. Everything after those n bits is never compared.

**2. Call that check H_n(x) = prefix_n(H(x)).**
H(x) is the full SHA-256 digest. prefix_n keeps the first n bits. Say the formula once, left to right.

**3. Any second message with the same prefix verifies under the same signature.**
The signature is compared with the prefix. A second message that lands on that prefix is accepted.

If asked: the signature did the comparison it was given. The weakness is how little of the digest that comparison uses.

**4. We measure how large n has to be before finding such a pair stops being practical.**
Small n is a search we can finish. The result of the talk is the largest n we can still finish.

## Slide 3 — What the talk covers

**1. What truncation removes, and which bits are kept.**
Next slides: the formula, then the picture of the leftmost bit. The kept bits are the leading ones.

**2. Why the cost is 2^(n/2), not 2^n and not 2^128.**
A collision search costs the square root of the number of prefixes. 2^n would be trying every prefix. 2^128 is the birthday cost of the full 256-bit digest.

**3. Five ways to search: hash table, Floyd, distinguished points, parallel chains, meaningful messages.**
Same event each time: two inputs, one prefix. Say how each one differs before leaving the bullet.

- Hash table stores every prefix and the first message that made it. Memory grows like 2^(n/2) rows, and the repeat is noticed on the hash that creates it.
- Floyd stores two pointers. The tortoise takes one step, the hare takes two, and memory stays flat. The cost shows up as hashes.
- Distinguished points use Floyd's step, and store a state only when its lowest d bits are zero. d = n/4. A larger d means a longer walk and a smaller table.
- Parallel runs one of those searches on 4 processes. The hash table and the meaningful messages split the counter, Floyd starts one walk per process, and distinguished points split the chains. The parent merges what the processes return. Wall-clock time is what changes. The parent still holds the table.
- Meaningful messages keep two sentences fixed, a letter and an order, and change only an eight-digit serial. A reader sees two texts. H_n sees one prefix. The cost is the same birthday cost.

**4. The largest n the machine can still break, and what that means for the signature.**
That number is the security answer. A broken n is a prefix a signature cannot separate.

If asked for the number now: it is on the slide "How far the prefix can go," after the pictures.

## Slide 4 — SHA-256

**1. SHA-256 is one function in the SHA-2 family. Its digest is 256 bits, 64 hex digits.**
SHA-2 also has SHA-224, SHA-384, and SHA-512. We used SHA-256. 256 bits is 64 hex digits, because each hex digit is 4 bits.

**2. It is built to be collision resistant and preimage resistant.**
Collision resistance: hard to find any two messages with the same digest. Preimage resistance: given a digest, hard to find a message that produces it. This talk is the collision side.

**3. Full SHA-256 is used in signatures, TLS, and blockchains.**
Those systems rely on the full digest. Our result applies when a check throws part of that digest away.

**4. We do not attack the compression function. We attack the prefix a verifier chose to keep.**
The hash rounds stay as SHA-256 defines them. The attack starts after the digest exists, at the bits the verifier deleted.

If asked "is SHA-256 broken?": the full digest still has a birthday cost of 2^128. The break is of the shortened check.

## Slide 5 — Truncation

**H_n(x) = prefix_n(H(x))**
Read it as "the n-bit prefix of the SHA-256 digest of x."

**1. H(x) is the full SHA-256 digest.**
32 bytes. Every search in the program starts from that digest.

**2. The prefix is the most significant n bits: the leading hex digits.**
Most significant means the left end when the digest is written in hex. The next slide is the picture of that.

**3. For n = 32, that is the first 8 hex digits. The other 56 digits are discarded.**
8 digits because 32 / 4 = 8. The signature never sees the remaining 56.

**4. Every bit dropped from the prefix halves the birthday cost.**
One less bit halves the number of possible prefixes, and the birthday cost is the square root of that number, so the work halves too.

If asked why anyone truncates: to save space. The security claim shrinks with the prefix. n = 32 leaves about 16 bits of collision security.

## Slide 6 — Which bits are the prefix?

**The byte picture: 0 1 1 0 0 1 0 0, written left to right.**
This is the lecture's example byte. Walk one box at a time, left to right.

**MSB under the first bit, LSB under the last.**
MSB is the most significant bit, place value 2^7. LSB is the least significant bit, place value 2^0. The byte's value is 64 + 32 + 4 = 100, so the left bits dominate.

**The lecture byte is 01100100. The leftmost bit is the most significant bit.**
Say that sentence as written. It fixes the direction for the rest of the talk.

**H_n keeps that same left-hand end of the 256-bit digest.**
Scale the picture up from 8 bits to 256. The prefix is that same left end. For a multiple of 4, H_n is the first n/4 hex digits. The later pictures use n = 16, four hex digits, so the labels fit. At n = 32 the same pictures keep eight digits.

## Slide 7 — A collision, and what it costs

**x ≠ x' and H_n(x) = H_n(x').**
Two conditions, both required. The messages differ. Their prefixes match. Read the formula before the bullets.

**1. The generic attack is the birthday attack. Its cost is O(2^(n/2)).**
Take random messages and wait for a repeated prefix. With about 2^(n/2) messages, a repeat is expected. The square comes from pairs: k messages make about k^2 / 2 pairs, and that meets 2^n when k is about 2^(n/2).

**2. Truncation leaves at most n/2 bits of collision security.**
A 32-bit prefix leaves 16 bits of collision security. A 256-bit digest leaves 128.

**3. Full SHA-256 has n = 256, so the same bound is 2^128.**
Same formula, full width. That is why the full hash is the strong case on the next table.

**4. A search that only matches 2^(n/2) is already enough. Beating it would be an attack on SHA-256 itself.**
We measure the generic cost. Landing on that cost answers the assignment. A method that finished much faster would be a result about SHA-256, and we do not have one.

## Slide 8 — Lecture markers

Read the table by rows. The last column is the one to linger on.

**n = 32, cost 2^16, 8 hex digits, short and practical.**
About 65 thousand hashes. A laptop finishes this. This is where we start.

**n = 64, cost 2^32, 16 hex digits, short and still a target.**
About 4 billion hashes. Still the lecture's short-prefix example. The table of a hash-table search no longer fits comfortably.

**n = 128, cost 2^64, 32 hex digits, the example that stays large.**
This is the lecture's marker for a prefix that is still too big to walk.

**n = 256, cost 2^128, 64 hex digits, full SHA-256.**
The untruncated digest. Same formula, full length.

**We start at n = 32 and move upward. The result that matters is the largest n we can still finish.**
A collision at n = 16 shows the program works. Collisions exist at every length. The security question is the cost, and the largest length whose cost still fits.

## Slide 9 — What the signature actually checks

**1. The signer signs H_n(x), not the other 256 − n bits.**
The signed value is the prefix. The dropped bits are absent from the signature.

**2. The verifier hashes the message it received and compares the leading n bits with the signature.**
Whatever file shows up, the verifier hashes that file and looks at the front of the digest.

**3. If x and x' share that prefix, a signature on x verifies on x'.**
This is the attack. Find the pair first. Obtain a signature on the message you can show people. The other message verifies under it.

**The signature is only as collision resistant as H_n.**
Read this line last. It is the sentence the three steps add up to.

If asked about keys: no key is stolen. The substitution works because the verifier's comparison succeeds.

## Slide 10 — Alice, as the analogy

**1. Daum and Lucks published two PostScript files a person reads as different documents.**
This is the historical poisoned-message story. Two files, one digest, two meanings for a human reader.

**2. One is a letter of recommendation. The other is an order that grants access.**
Same pair of meanings we use later for the meaningful-message search. Here they are PostScript, and the hash is MD5.

**3. They share one MD5 digest, a25f7f0b29ee0b3968c860738533a4b9.**
Point at the digest. It is the published value. We cite it. We do not recompute it.

**4. A signature on the letter is a valid signature on the order.**
The verifier checks the digest. Both files have that digest, so one signature covers both.

**5. We cite that pair. We do not recompute MD5. Our search is the same story for a prefix of SHA-256.**
Their attack is a dedicated MD5 collision. Ours is the birthday search on a SHA-256 prefix. The idea that transfers is one accepted hash value, two documents.

If asked how the MD5 pair was built: that construction is theirs. This project searches prefixes of SHA-256.

## Slide 11 — One search, five ways to run it

**Sample inputs until two of them share an n-bit prefix.**
One sentence for the whole table. Every row is that search.

Then one row at a time. Column "What is stored" is the method. Column "What grows" is the cost.

**Hash table — every prefix, and the first message. Memory grows, about 2^(n/2) rows.**
Write a row for each new prefix. The table is the large object.

**Floyd — two pointers. Hashes grow, memory stays flat.**
Tortoise and hare. Almost nothing is stored.

**Distinguished points — one state every 2^d steps. Both grow, and d chooses the mix.**
Store less often than the hash table. Walk longer than Floyd. d is the knob.

**Parallel — the chosen search, split across processes. Wall-clock time is what changes.**
Menu 4 asks which algorithm. Four processes share that algorithm. The collision is the same kind of collision.

**Meaningful messages — letter serials, then orders. Same birthday cost.**
The messages are sentences. The cost formula does not change.

If asked why five methods: they are the time–memory choices the problem asks for, plus the parallel runs of those algorithms. They are one attack.

## Slide 12 — Hash table

**1. Messages are the decimal counters "0", "1", "2", …**
The counter starts at 0. The message is the decimal text, so "0" is the character 0x30. A second run walks the same messages and finds the same pair.

**2. Store the leading n bits, and the first message that produced them.**
The key is the prefix. The value is the message. A new prefix becomes a new row.

**3. The first repeated prefix is the collision.**
The new message and the stored message are the pair. There is no cycle and no second pointer in this method.

**4. Memory is one row per new prefix, so about 2^(n/2) rows.**
That is the birthday number of messages, and each of them occupies a row until the repeat.

**5. This is the memory-heavy end of the tradeoff. It is also the method that finishes a short prefix soonest.**
You notice the repeat on the hash that creates it. The table is why a larger n runs out of RAM here first.

## Slide 13 — Hash table, on real SHA-256

Walk the picture from the top.

**SHA-256("251") keeps c75d and drops 3f1f…**
Real SHA-256 of the text "251". The box c75d is the prefix that is kept. The box 3f1f… is the rest of the digest, and it is dropped. The two messages can differ in those dropped digits.

**Rows: 5fec with "0", 6b86 with "1", c75d with "157".**
"0" and "1" are ordinary new rows. "157" is the first message stored under c75d. A new prefix is a new row, and that row is not yet a collision.

**"251" points up to c75d, labeled "same leading bits."**
"251" produces c75d again. "157" and "251" are the collision. Point at the arrow.

**Blue is stored. Orange is the collision.**
Blue marks a prefix that sits in the table. Orange marks the two inputs that share one prefix.

**At n = 32 the same picture keeps eight hex digits.**
This drawing uses 16 bits, four hex digits, so the labels fit. The rule is the same at n = 32. Only the stored prefix is wider.

## Slide 14 — Floyd

**1. The state is an n-bit block. Hash it, keep the leading n bits, and that block is the next state.**
This does not hash the strings "0", "1", "2". It hashes a state and feeds the prefix back in as the next state. Each arrow on the next slide is one such step.

**2. The tortoise takes one step. The hare takes two. They meet on the cycle.**
Two pointers on one chain. The hare gains one step per round, so it meets the tortoise somewhere on the loop.

**3. Walk back to the entrance. The two states that both step onto that entrance are the collision.**
The meeting point is on the cycle. The entrance is where the tail hits the cycle. The collision is the two different states with that entrance as their next value.

**4. Only the two pointers are kept. Memory stays essentially constant.**
No table of states. The memory does not grow with n.

**5. The number of hashes is still on the order of 2^(n/2).**
You pay in hashes for the flat memory. The extra walk back to the entrance is a small constant on top of that.

If asked about a retry: if both predecessors are the same state, that start is a pure cycle. The program tries the next seed.

## Slide 15 — Floyd, on a short chain

**The chain 0 → 1 → 2 → 3 → 4 → 5 → 3.**
A teaching chain, drawn so the loop is visible. Follow it left to right, then the return from 5 to 3.

**Entrance on state 3.**
3 is where the chain joins the loop. The tortoise and the hare are how you find that node without storing the chain.

**State 2, "one step to 3." State 5, "one step to 3."**
Both orange nodes step onto 3. They are the collision. 3 itself is the shared next state.

**Each arrow is one SHA-256 step. States 2 and 5 are the collision. Nothing in this picture is written to a table.**
Read the caption. Nothing is blue, because Floyd stores the pointers and not the nodes.

If asked how this differs from the hash-table picture: there the orange messages hash to a stored row. Here the orange states step onto the entrance, and the entrance is not a stored record.

## Slide 16 — Distinguished points

**1. Same step as Floyd: hash the state, keep the leading n bits.**
The chain is the same kind of chain. The change is when a state is written down.

**2. Store a state only when its lowest d bits are zero. We use d = n/4.**
d is the knob from the table on slide 11. Larger d means a longer gap between stored states and a smaller table.

**3. For d = 4, that test is "the last hex digit is 0."**
Four zero bits are one hex digit. The next picture uses that test. The stored value is still the full n-bit state. d decides how often a row is written, not how wide the row is.

**4. The table holds the endpoint and the chain start. Intermediate states are dropped.**
The endpoint is the first state on the chain whose low bits are zero. The start is kept so the chain can be walked again. Everything between them is discarded.

**5. A second chain with the same endpoint is recomputed from both starts. The two messages that first meet are the collision.**
A repeated endpoint means the chains merged somewhere earlier. Walk both from their saved starts. The first shared state ends the walk. The two states that stepped onto it are the collision.

## Slide 17 — Distinguished points, on real SHA-256

**c251 and de75 both point to fbfe.**
Real SHA-256, n = 16. Those two orange states both step to fbfe. They are the collision.

**fbfe → cc55 → cc9b → fca0.**
The chain continues after the collision. fbfe ends in e, cc55 ends in 5, cc9b ends in b. Those three are computed and dropped.

**fca0, "ends in 0, stored."**
The last hex digit is 0, so the lowest four bits are 0000. That passes d = 4. fca0 is the only blue node, the only table entry, and the chain stops there.

**n = 16, d = 4. c251 and de75 both step to fbfe. Only fca0 is stored. The chain stops there.**
Read the caption after the picture. A second chain that arrives at the same fca0 is the signal to walk both starts again and recover c251 and de75. The walk does not continue past fca0.

If asked why the pattern is a trailing zero: it is the pattern we chose for "lowest d bits are zero." Another pattern of d zero bits would mark endpoints the same way. A longer gap between stored points means less memory and more hashing before the merge is noticed.

## Slide 18 — Time against memory

**1. Hash table: spend memory, detect the repeat as soon as it appears.**
The repeat is visible on the hash that creates it, because every earlier prefix is still in the table.

**2. Floyd: spend hashes, keep two pointers.**
The other end of the scale. Memory stays flat. The hashes follow 2^(n/2).

**3. Distinguished points sit between them. Larger d means a longer walk and a smaller table, about 2^(n/2 − d) endpoints.**
d moves you along the scale. Each stored point stands for about 2^d steps. The number of stored endpoints drops by that same factor.

**4. Menu 4 asks which algorithm to run on several processes.**
This is the problem's "parallelize your algorithms." It is the same searches, on 4 processes. It is a way to spend cores. It is a separate choice from d.

**5. The hash table and the meaningful messages split the counter, and the parent merges prefixes. Floyd starts one walk per process. Distinguished points split the chains.**
Hash table and meaningful messages: each process takes a share of the counter, and the parent owns the prefix table. Floyd: each process has its own seed. Distinguished points: each process walks its own chains, and the parent merges endpoints. The parent still holds the table, so four processes do not divide the memory by four. On a tiny n, starting the processes costs more than the hashing. The time drops when the search is long. Two processes can still hash overlapping work.

## Slide 19 — Meaningful messages

**1. The two texts stay fixed. Only an eight-digit serial at the end changes.**
The free part is the serial. The words do not change between attempts.

**2. One text is a letter of recommendation. The other is an order that grants access.**
A person reads them as different documents. Same pair of meanings as Alice's story. The bytes are these two sentences, with a serial, rather than the PostScript files.

**3. Letter serials fill a table of prefixes. The first matching order serial is the collision.**
Hash the letter serials and store the prefix. Hash order serials until a prefix is already there. That letter and that order are the pair.

**4. A reader sees two different sentences. H_n sees one prefix.**
The person distinguishes the sentences. The truncated check does not.

**5. This is the birthday construction with a free serial. It is not the MD5 PostScript construction.**
The cost is the same 2^(n/2). The MD5 pair on the Alice slide stays a citation. If a later lecture gives a tighter document construction, this is the version we can already run, and the security conclusion already follows from a colliding prefix.

## Slide 20 — What "verified yes" means

**After a search returns, the program hashes both messages again and checks three things.**
The search returning a pair is not the check. The printer hashes both messages again.

**1. The two messages are different.**
Identical bytes would be one message written twice. The program rejects that.

**2. Their leading n bits match each other.**
Both fresh digests are truncated. The prefixes have to agree.

**3. Those bits match the prefix the search stored.**
The fresh prefix has to equal the prefix the search claimed. This catches a wrong value stored in the table.

**The check is a fresh SHA-256 of each message. It does not trust the table.**
"Verified yes" means all three passed. The time on that printout is the wall-clock time of the search. The memory is the peak traced memory. A line that says "not recorded" means that run did not measure it.

## Slide 21 — What to take from a run

**For every finished (n, method), keep four numbers and the pair.**
One row of results per finished run. Say which run you are quoting.

**Hashes — compare with 2^(n/2).**
The count should sit near the birthday cost. A count near 2^n would mean the search tried the whole prefix space.

**Time — the practical cost.**
Seconds on the machine that ran it. This is the number a person uses to decide "practical."

**Peak memory — which side of the tradeoff this method is on.**
At the same n, the hash table's number is large and Floyd's stays near a constant.

**Shared prefix — the value the signature would accept.**
This is the H_n value in the signature story.

**Same n, different methods: the hash table should use much more memory, and Floyd should stay near a constant.**
Compare methods at one n. A hash table at n = 16 against a Floyd run at n = 32 is two different problems. For a live demo, n = 16 or n = 32 is enough, and you read the four numbers off the screen.

## Slide 22 — How far the prefix can go

**1. n = 32: about 2^16 hashes. A hash table fits and finishes.**
About 65 thousand hashes. This is the first length the lecture calls practical, and it is a length we can show.

**2. n = 48: about 2^24 hashes. The hash table is large. This is a plausible largest length for that method.**
About 16 million hashes. Call it finished only if the run you have actually finished. A hash-table run stays quiet until the first repeated prefix. Several quiet minutes is the search working.

**3. n = 64: about 2^32 hashes and, for the hash table, about four billion rows. Memory runs out before a hit.**
Stop a hash-table run at this length. RAM is the wall. Waiting does not get past a table of that size.

**4. Floyd still stores two pointers at n = 64. Time is then the wall, not RAM.**
The pointers stay two pointers. The cost that grows is the hashing, about 2^32 steps.

**5. n ≥ 128: birthday cost at least 2^64. That is the lecture's example of a prefix that remains large.**
This matches the table on the lecture-markers slide. It is the length we describe with the formula and do not claim to have walked.

The largest n you personally finished is the number to defend.

## Slide 23 — The security answer

**1. For every n we break, a signature on H_n does not separate the two inputs.**
We have two messages and one prefix. The signature check accepts both. Say this for the lengths you actually finished.

**2. n = 32 and n = 64 are the short prefixes. Their costs, 2^16 and 2^32, are the practical attack.**
These are the lecture's short prefixes. 2^16 finishes here. 2^32 is the lecture's other short-prefix cost. Say how far along that cost you got.

**3. n ≥ 128 is still only a theoretical birthday attack on this machine.**
The formula still says 2^64 or more. That did not finish on this machine.

**4. The deciding attack is the birthday bound on the prefix, not a dedicated break of SHA-256.**
This is the conclusion the topic asks for. Practical means it finishes on the machine we have, with a method we can describe.

## Slide 24 — Close

**1. Truncation cuts collision security from 128 bits to n/2 bits.**
Full SHA-256 gives 2^128 birthday work. A prefix of n bits gives 2^(n/2). Say the largest n you are willing to claim, then sit down.

**2. The hash table buys speed with memory. Floyd buys a flat memory cost with more hashing. Distinguished points choose a point in between. Parallel runs any of those searches on several processes.**
One sentence per method, in the order the talk used them. Parallel is menu 4, across the searches, on several processes.

**3. The largest n we finish is the point where this signature stops being a practical protection.**
Tie the measurement back to the signature on slide 9.

**4. Two readable messages with one prefix show why that matters to a person, not only to a counter.**
The letter and the order. A person accepts them as different documents. H_n accepts them as one prefix.

Slides 25 and 26 are for questions.

## Slide 25 — Backup: one hash-table pair at n = 32

**Messages are the decimal strings 95303 and 69235.**
Say the decimal strings. Their ASCII hex on a printout is 3935333033 and 3639323335.

**1. Shared prefix: c11eb5e6.**
Both SHA-256 digests start with these eight hex digits. Point at the prefix.

**2. Hashes: 95,304.**
That is the number of SHA-256 evaluations in the hash-table run that found this pair.

**3. Birthday scale: 2^16 = 65,536.**
95,304 is the same scale as 65,536. The search landed where the birthday bound said it would.

**Use the prefix, time, and memory printed by the run you present. Replace this pair if a later run is the one you keep.**
Read this line if your demo run is a different pair. Prefer the run you can show.

## Slide 26 — Backup: sources

**1. Magnus Daum and Stefan Lucks, Hash Collisions (The Poisoned Message Attack), and the URL on the slide.**
The Alice slide cites this. The URL is the copy used in the course.

**2. NIST, Secure Hash Standard (SHS), FIPS PUB 180-4, 2015.**
The definition of SHA-256.

**3. Code: code/main.py. Choice 4 asks which of the four searches to run on 4 processes. The prefix length must be a multiple of 8.**
Menu: 1 hash table, 2 Floyd, 3 distinguished points, 4 parallel and then which algorithm, 5 meaningful messages, 6 exit. n is a multiple of 8, from 8 to 256. A live demo at n = 16 finishes quickly. n = 32 is the first lecture length. Skip a hash-table demo at n = 64.
