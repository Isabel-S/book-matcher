def _zeros(n_rows, n_cols):
    """Create a 2D list of zeros with dimensions (n_rows x n_cols)."""
    return [[0 for _ in range(n_cols)] for _ in range(n_rows)]

def WagnerFischer(A, B, insertion=1, deletion=1, substitution=1):
    """Generalized Wagner-Fischer for arbitrary sequences (not just strings)."""
    n_A = len(A)
    n_B = len(B)

    D = _zeros(n_A + 1, n_B + 1)

    # Initialize edges
    for i in range(n_A):
        D[i + 1][0] = D[i][0] + deletion
    for j in range(n_B):
        D[0][j + 1] = D[0][j] + insertion

    # Fill matrix
    for i in range(n_A):
        for j in range(n_B):
            if A[i] == B[j]:
                D[i + 1][j + 1] = D[i][j]  # match (free)
            else:
                D[i + 1][j + 1] = min(
                    D[i + 1][j] + insertion,    # insert
                    D[i][j + 1] + deletion,     # delete
                    D[i][j] + substitution      # substitute
                )

    # Traceback
    aligned_A = list(A)
    aligned_B = list(B)
    changes = []

    i, j = n_A, n_B
    while i > 0 and j > 0:
        s_cost = D[i][j]
        d_cost = D[i-1][j]
        i_cost = D[i][j-1]

        if s_cost <= d_cost and s_cost <= i_cost:
            if A[i-1] == B[j-1]:
                changes.append('=')
            else:
                changes.append('*')
            i -= 1
            j -= 1
        elif d_cost < i_cost:
            changes.append('v')
            aligned_B.insert(j, '*')  # mark missing element in B
            i -= 1
        else:
            changes.append('^')
            aligned_A.insert(i, '*')  # mark missing element in A
            j -= 1

    # Remaining characters if any
    while i > 0:
        changes.append('v')
        aligned_B.insert(0, '*')
        i -= 1
    while j > 0:
        changes.append('^')
        aligned_A.insert(0, '*')
        j -= 1

    return aligned_A, aligned_B, ''.join(reversed(changes))

book_database = [
    ["DT 515.9 .A17 B94 2021", "Byfield", "The Great Upheaval"],
    ["DT 515 .A612 V.18 NO.1 MAR 2022", "Academic Scholarship Journal"],
    ["DT 515.9 .B585 S74 1993", "Stewart", "Borgu and Its Kingdoms"],
    ["F1408.3 .B87 2011 V.3", "La Busqueda Perpetua..."],
    ["DT 515.8 .K49 2008", "After NYSC What Next?"],
    ["DT 512.32 G53 2007", "Ghana"],
    ["F 1316 .M44 2012", "McEnroe", "From Colony to Nationhood in Mexico"],

    # sequential placeholders for the seven “my first …” picture books
    ["No call 0", "my first book of colors"],
    ["No call 1", "my first book of food"],
    ["No call 2", "my first book of shapes"],
    ["No call 3", "my first book of abc"],
    ["No call 4", "my first book of toys"],
    ["No call 5", "my first book of wild animals"],
    ["No call 6", "my first book of birds"],

    ["QA402 .O63 1997", "Oppenheim & Willsky & Nawab", "Signals & Systems", "2nd ed."],           # :contentReference[oaicite:0]{index=0}
    ["Q335 .R411 1989", "Mylopoulos & Brodie", "Readings in Artificial Intelligence & Databases"],   # :contentReference[oaicite:1]{index=1}
    ["Q335 .R86 2021", "Russell & Norvig", "Artificial Intelligence: A Modern Approach"],            # :contentReference[oaicite:2]{index=2}
    ["TK5105.5 .P47 2022", "Peterson & Davie", "Computer Networks: A Systems Approach", "6th ed."],  # :contentReference[oaicite:3]{index=3}
    ["PL873.K392 B4413 2020", "Kawaguchi", "Before the Coffee Gets Cold"],
    ["ML420.Z3913 A3 2021", "Zauner", "Crying in H Mart"],                                           # :contentReference[oaicite:4]{index=4}
    ["PS3619.T744 Z46 2012", "Strayed", "Wild"],                                                     # :contentReference[oaicite:5]{index=5}
    ["QA76.758 .R53 1986", "Rich & Waters", "Readings in Artificial Intelligence & Software Engineering"],
    ["QA76.9.A73 P377 2019", "Hennessy & Patterson", "Computer Architecture: A Quantitative Approach"],  # :contentReference[oaicite:6]{index=6}
    ["RC280.L8 K35 2016", "Kalanithi", "When Breath Becomes Air"],                                    # :contentReference[oaicite:7]{index=7}
    ["Q335 .P66 2010", "Poole & Mackworth", "Artificial Intelligence: Foundations of Computational Agents"],
    ["Q335 .A14 2022", "AI Engineering", "AI Engineering"],
    ["TK5105.5 .B66 2021", "Bonaventure", "Computer Networking: Principles, Protocols & Practice"],
    ["GT2918 .M67 2019", "Morris", "Coffee: A Global History"],                                      # :contentReference[oaicite:8]{index=8}
    ["TX724.5.K65 W44 2023", "Wegman", "H Mart Recipes"],
    ["CT9971.M38 K73 1997", "Krakauer", "Into the Wild"],                                            # :contentReference[oaicite:9]{index=9}
    ["QA76.9.A73 M66 2022", "Mullins & Moore", "Modern Computer Architecture"]
]

book_database={"0": {"alt_title": "\u5e7f\u4e1c\u767e\u79d1\u5168\u66f8;", "call_number": "DS793.K7 K8446 1995", "lang": "CHN"}, 
               "1": {"alt_title": "\u5e7f\u4e1c\u5386\u53f2:\u4e61\u571f\u6559\u6750", "call_number": "DS793 .K7 K847 1978", "lang": "CHN"}, 
               "2": {"alt_title": "\u5e7f\u4e1c\u7701\u5e02\u5730\u53bf\u6982\u51b5", "call_number": "DS793.K7 K8477 1985", "lang": "CHN"}, 
               "3": {"alt_title": "\u5e7f\u4e1c\u4e61\u571f\u5730\u7406:\u5e7f\u4e1c\u7701\u4e2d\u5b66\u8bd5\u7528\u8bfe\u672c", "call_number": "DS793 .K7 K848 1979", "lang": "CHN"}, 
               "4": {"alt_title": "\u5dba\u5357\u6587\u5316\u65b0\u63a2\u7a76\u8ad6\u6587\u96c6", "call_number": "DS793.K7 K85 1996", "lang": "CHN"}, 
               "5": {"alt_title": "\u5ee3\u6771\u9109\u571f\u5730\u7406\u6559\u79d1\u66f8", "call_number": "DS793 .K7 K86, V.1-2   ", "lang": "CHN"}, 
               "6": {"alt_title": "\u5e7f\u4e1c\u5386\u53f2\u4eba\u7269\u8f9e\u5178", "call_number": "DS793.K7 K87 2001", "lang": "CHN"}, 
               "7": {"alt_title": "\uff08\u842c\u66c6\uff09\u7ca4\u5927\u8a18:32\u5377", "call_number": "DS793.K7 K88 1990", "lang": "CHN"}, 
               "8": {"alt_title": "\u5ee3\u6771\u7701\u5fd7.\u6587\u5316\u827a\u672f\u5fd7", "call_number": "DS793 .K7 K91402 2001 ", "lang": "CHN"}, 
               "9": {"alt_title": "\u5e7f\u4e1c\u7701\u5fd7.\u65c5\u6e38\u5fd7", "call_number": "DS793 .K7 K91403 1999 ", "lang": "CHN"}}


if __name__ == "__main__":
    print(WagnerFischer([1,2,3,4,5], [100,3,5]))
    print(WagnerFischer([1,2,3,4,5,6], [1,2,4,3,100,5]))