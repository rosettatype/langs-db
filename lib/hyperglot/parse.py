import unicodedata2
import logging
import re
from fontTools.ttLib import TTFont

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def list_unique(li):
    """
    Return unique list items while maintaining order
    """
    if type(li) is not list:
        raise ValueError("list_unique expected list, but got '%s' of type '%s'"
                         % (li, type(li)))
    seen = set()
    seen_add = seen.add
    return [x for x in li if not (x in seen or seen_add(x))]


def character_list_from_string(string, normalize=True):
    """
    Return a list of characters without space separators from an input string
    """

    # Since Unicode allows writing the same string either precomposed or as
    # combining characters, we want to transform all those strings that are
    # written as combining characters to precomposed, if possible. In our
    # data a combining char (be it encoded as precomposed or with
    # combining marks) means we want to explicitly check
    # a) the combining marks, and
    # b) with flag we want to check the precomposed unicode is present - and
    # for this we need to make sure our data input with combing marks is
    # actually interpreted (and re-saved) as precomposed!

    # Before splitting a string into a list of each character (and removing
    # spaces) make sure any composable characters written with combining marks
    # are in fact transformed to precomposed characters; otherwise the
    # "listifying" will split base and mark(s) into several list items (chars)
    if normalize:
        # Make sure we are in fact dealing with a string, not a list
        if isinstance(string, list):
            string = "".join(string)

        # N_ormal F_orm C_omposed
        # See more https://docs.python.org/3/library/unicodedata.html#unicodedata.normalize # noqa
        string = unicodedata2.normalize("NFC", string)
    li = list(string)
    li = list_unique([c for c in li if c.strip() != ""])
    return li


def parse_chars(characters, decompose=True, retainDecomposed=False):
    """
    From a string of characters get a set of unique unicode codepoints needed
    Note this will "decompose" combinging characters/marks and remove any
    standard whitespace characters (space, line break) but treat special
    whitespace characters as part of the charset (e.g. non breaking, enspace,
    etc.)
    Use this on all orthography base/auxiliary data
    """
    unique_chars = []
    try:
        unique_strings = "".join(character_list_from_string(characters))

        if not decompose:
            # If we want to just get the string of characters as a list without
            # doing any decomposition return a list of unique, space separated,
            # strings
            return character_list_from_string(unique_strings)

        for c in unique_strings:

            # decomposition is either "" or a space separated string of
            # zero-filled unicode hex values like "0075 0308"
            decomposition = unicodedata2.decomposition(c)

            # This glyph should be part of the list if either it cannot be
            # decomposed or if we want to keep also decomposable ones (e.g.
            # when pruning and saving the DB)
            if decomposition == "" or retainDecomposed:
                unique_chars.append(c)

            ignore = ["<isolated>", "<compat>", "<super>", '<vertical>']
            if decomposition != "":
                for unihexstr in decomposition.split(" "):
                    # Not _entirely_ sure why the following can be parts of the
                    # decomposition but let's ignore them when encountered
                    if unihexstr in ignore:
                        continue
                    try:
                        unique_chars.append(chr(int(unihexstr, 16)))
                    except Exception as e:
                        log.error("Error getting glyph from decomposition "
                                  "part '%s' of '%s' (decomposition '%s'):"
                                  " %s" % (unihexstr, c, decomposition, e))

        unique_chars = list_unique(unique_chars)
    except Exception as e:
        log.error("Error parsing characters '%s': %s" % (characters, e))

    return [u for u in unique_chars if not re.match(r"\s", u) and len(u) != 0]


def prune_superflous_marks(string):
    """
    From a given string return a set of unique characters with all those
    standalone Mark charaters removed that are already implicitly present in
    a decomposable character

    @param string str
    @return set pruned, set removed
    """
    unique_strings = character_list_from_string(string)
    removed = []

    for c in unique_strings:
        # No need to bother about glyph clusters with more than one character,
        # since that inherently will not be a mistakenly listed mark
        if len(c) > 1:
            continue
        if unicodedata2.category(c).startswith("M"):
            for s in unique_strings:
                if s != c and c in parse_chars(s):
                    removed.append(c)

    if removed == []:
        return unique_strings, ()

    pruned = [c for c in unique_strings if c not in removed]
    removed = list_unique(removed)

    return pruned, removed


def parse_font_chars(path):
    """
    Open the provided font path and extract the codepoints encoded in the font
    @return list of characters
    """
    font = TTFont(path, lazy=True)
    cmap = font["cmap"]
    font.close()

    # The cmap keys are int codepoints
    return [chr(c) for c in cmap.getBestCmap().keys()]
