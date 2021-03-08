"""
This is just a temporary file to try to implement camel case
to snake case names converting. May be removed later
"""


def camelcase2snake(string):
    words = [string[0]]

    for letter in string[1:]:
        previous_letter = words[-1][-1]

        if letter.isupper() and not previous_letter.isupper() and \
                not previous_letter.isdigit():
            words.append(letter)
        elif not letter.isupper() and previous_letter.isupper() and \
                (len(words[-1]) > 1 and not words[-1][-2].isdigit()):
            words[-1] = words[-1][:-1]

            if not words[-1]:
                words.pop()

            words.append(previous_letter + letter)
        else:
            words[-1] += letter

    return '_'.join(map(lambda element: element.lower(), words))


print(camelcase2snake('ParseHTMLPage'))
print(camelcase2snake('One2Many'))
