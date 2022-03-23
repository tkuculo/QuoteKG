from model.entity_quotes import *
from model.utils import *
from pathlib2 import Path
from requests.utils import requote_uri
import pandas as pd

import re

from rdflib.namespace import DCTERMS, OWL, \
    RDF, RDFS, SKOS, XSD
from rdflib import Namespace
from rdflib import Graph
from rdflib import URIRef, Literal
from rdf.ns_QKG import QKG

all_languages = ["aa", "ab", "ae", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az", "ba", "be", "bg", "bh", "bi",
                 "bm", "bn", "bo", "br", "bs", "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy", "da", "de", "dv",
                 "dz", "ee", "el", "en", "eo", "es", "et", "eu", "fa", "ff", "fi", "fj", "fo", "fr", "fy", "ga", "gd",
                 "gl", "gn", "gu", "gv", "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz", "ia", "id", "ie", "ig",
                 "ii", "ik", "io", "is", "it", "iu", "ja", "jv", "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko",
                 "kr", "ks", "ku", "kv", "kw", "ky", "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv", "mg", "mh",
                 "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr",
                 "nv", "ny", "oc", "oj", "om", "or", "os", "pa", "pi", "pl", "ps", "pt", "qu", "rm", "rn", "ro", "ru",
                 "rw", "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su",
                 "sv", "sw", "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty", "ug",
                 "uk", "ur", "uz", "vi", "vo", "wa", "wo", "xh", "yi", "yo", "za", "zh", "zu"]

current_date = (2021, 21, 3)  # this needs to be synchronised with erroneous results from datefinder (yyyy, mm,dd)

pattern_brackets = re.compile(
    r'\[[^\]]*\]')  # https://stackoverflow.com/questions/640001/how-can-i-remove-text-within-parentheses-with-a-regex
pattern_brackets2 = re.compile(
    r'\([^\)]*\)')  # https://stackoverflow.com/questions/640001/how-can-i-remove-text-within-parentheses-with-a-regex

pattern_ref = re.compile(r'<ref[^<]*</ref>')
pattern_ref2 = re.compile(r'<ref>[^<]*$')
pattern_ref3 = re.compile(r'<ref[^>]*/>')
pattern_small = re.compile(r'<small[^<]*</small>')
pattern_small2 = re.compile(r'<small>[^<]*$')
pattern_small3 = re.compile(r'<small[^>]*/>')

pattern_multiple_spaces = re.compile(r' +')


class RDFEntity:
    def __init__(self, uri):
        self.uri = uri
        self.types = set()
        self.wikiquoteIds = dict()
        self.wikiquotePageIds = dict()
        self.wikidata_id = None
        self.labels = dict()


def cleanText(text, isQuote=False):
    # remove everything in []
    text = re.sub(pattern_brackets, "", text)

    # remove everything in "()" if it is quote text (not in context)
    if isQuote:
        text = re.sub(pattern_brackets2, "", text)

    # remove everything in "<ref"
    text = re.sub(pattern_ref, "", text)
    text = re.sub(pattern_ref2, "", text)
    text = re.sub(pattern_ref3, "", text)
    # remove everything in "<small"
    text = re.sub(pattern_small, "", text)
    text = re.sub(pattern_small2, "", text)
    text = re.sub(pattern_small3, "", text)
    # remove quotation marks at the start and end

    if text.endswith('".'):
        text = text[:-2] + '."'
    if text.endswith('».'):
        text = text[:-2] + '.»'

    text = text.strip('\"')
    text = text.strip('\\"')
    text = text.strip('"-”„«»')

    if line.startswith("原文:"):
        return line[3:]

    # remove any sequences of spaces
    text = re.sub(pattern_multiple_spaces, ' ', text)
    # strip spaces at begin and end
    text = text.strip()

    if text == "{{Citace monografie":
        text = None
    elif "Template:" in text:
        text = None

    return text


def createDateString(selected_date):
    year = str(selected_date[0])
    if len(year) > 4:
        return None
    while len(year) != 4:
        year = "0" + year

    month = selected_date[1]
    if month < 1 or month > 12:
        print("Error month:", month)
        return None
    month = str(month)
    if len(month) < 2:
        month = "0" + month

    day = selected_date[2]
    if day < 1 or day > 31:
        print("Error day:", day)
        return None
    day = str(day)
    if len(day) < 2:
        day = "0" + day

    return year + "-" + month + "-" + day


def aggregateSentiment(sentiments):
    scores = {}
    counts = {}
    for sentiment in sentiments:
        if sentiment["label"] in scores:
            scores[sentiment["label"]] = scores[sentiment["label"]] + sentiment["score"]
            counts[sentiment["label"]] = counts[sentiment["label"]] + 1
        else:
            scores[sentiment["label"]] = sentiment["score"]
            counts[sentiment["label"]] = 1
    max_score = max(scores, key=scores.get)
    return {"label": max_score, "score": scores[max_score] / counts[max_score]}


# print(cleanText("\"W1  W2 [2] [3] <ref>test</ref> W3 <ref mode='ccc'/> W4 <ref mode='aaa'>xyz</ref> W5 <small>"),
#      flush=True)

# a completeQuote object contains a quotes dictionary attribute, and an id attribute
# the quotes dictionary is composed of {language : quote}  pairs
# the quote value is an object of the class untemplatedQuote or of the class templatedQuote
# the quote object can contain different attributes depending on what was extracted, but 
# the string of the quote will always be in the quote attribute of the object

languages = ["si", "is", "sa", "vi", "da", "ka", "hi", "uz", "eu", "ku", "ro", "kn", "sq", "ml", "no", "cy", "be", "te",
             "ur", "th", "gl", "gu", "simple", "sr", "sah", "ta", "la", "ja", "nl", "ko", "hu", "li", "sv", "id", "nn",
             "su", "el", "hy", "hr", "ar", "bg", "et", "zh", "eo", "lt", "sl", "az", "fi", "ca", "tr", "bs", "sk", "he",
             "uk", "fr", "es", "pt", "de", "fa", "cs", "ru", "pl", "it", "en"]
languages.reverse()

SO = Namespace("https://schema.org/")
WD = Namespace("http://www.wikidata.org/entity/")
DBO = Namespace("http://dbpedia.org/ontology/")
ONYX = Namespace("http://www.gsi.upm.es/ontologies/onyx/ns#")
WNA = Namespace("http://gsi.dit.upm.es/ontologies/wnaffect/ns#")

wqCurid = dict()
wq = dict()
dbp = dict()
for lang in languages:
    wqCurid[lang] = URIRef("https://" + lang + ".wikiquote.org/wiki?curid=")
    wq[lang] = URIRef("https://" + lang + ".wikiquote.org/wiki/")
    dbp[lang] = "http://" + lang + ".dbpedia.org/resource/"

g = Graph()
g.bind("qkg", QKG)
g.bind("rdf", RDF)
g.bind("rdfs", RDFS)
g.bind("so", SO)
g.bind("owl", OWL)
g.bind("wd", WD)
g.bind("skos", SKOS)
g.bind("dbo", DBO)
g.bind("dcterms", DCTERMS)
g.bind("xsd", XSD)
g.bind("onyx", ONYX)
g.bind("wna", WNA)
<<<<<<< HEAD

pkl_file = "corpus/corpus.pkl"
wikiquote_to_wikidata_filename = "wikiquote_to_wikidata.tsv" # file generated by https://github.com/sgottsch/WikiquoteDumper/blob/main/src/de/l3s/cleopatra/quotekg/data/WikiquoteToWikidataMapCreator.java

print("Load Wikiquote to Wikidata mapping")

wikiquote_to_wikidata_mapping = dict()
with open(wikiquote_to_wikidata_filename) as file:
    for line in file:
        parts = line.rstrip().split("\t")
        language = parts[0]
        wikiquote_id = parts[2]

=======

pkl_file = "corpus.pkl"
wikiquote_to_wikidata_filename = "wikiquote_to_wikidata.tsv" # file generated by https://github.com/sgottsch/WikiquoteDumper/blob/main/src/de/l3s/cleopatra/quotekg/data/WikiquoteToWikidataMapCreator.java

print("Load Wikiquote to Wikidata mapping")

wikiquote_to_wikidata_mapping = dict()
with open(wikiquote_to_wikidata_filename) as file:
    for line in file:
        parts = line.rstrip().split("\t")
        language = parts[0]
        wikiquote_id = parts[2]

>>>>>>> 86e7569aea8d50ffd57ca4e3541721839ac5649e
        if wikiquote_id.startswith("Template:"):
            continue

        if language not in wikiquote_to_wikidata_mapping:
            wikiquote_to_wikidata_mapping[language] = dict()
        wikiquote_to_wikidata_mapping[language][wikiquote_id] = parts[3]

print("Load pkl file.", flush=True)
with open(pkl_file, "rb") as f:
    corpus = pickle.load(f)

# choose n to get list of all completeEntity objects with n aligned quotes

print("Data loaded.", flush=True)

completeQuoteId = 1
quotationId = 1
personId = 1
entityId = 1
contextId = 1
emotionSetId = 1
emotionId = 1

entity_dict = dict()
existing_quotes = dict()


# convert URLs in an RDF-friendly format
def cleanURL(url):
    return requote_uri(url)


# create "Context" object for templated quotations
def processTemplateContext(g, templateObject, contextURI, page_language):
    if isinstance(templateObject, str):
        text = cleanText(templateObject)
        if text:
            g.add((contextURI, QKG.contextText, Literal(text, page_language)))
    elif isinstance(templateObject, Line):
        text = cleanText(templateObject.text)
        if text:
            g.add((contextURI, QKG.contextText, Literal(text, page_language)))
        if templateObject.external_links:
            for external_link in templateObject.external_links:
                g.add((contextURI, SO.source, URIRef(cleanURL(external_link.uri))))


emotionCategoryDict = {"Neutral": URIRef(QKG) + "NeutralEmotion", "Positive": URIRef(QKG) + "PositiveEmotion",
                       "Negative": URIRef(QKG) + "NegativeEmotion"}
for emotionCategory in emotionCategoryDict:
    g.add((emotionCategoryDict[emotionCategory], RDF.type, ONYX.EmotionCategory))

invalid_section_titles = ["Ligações externas", "Vanjske poveznice", "Aiheesta muualla"]

# collect triples for all quotations
for completeQuote in corpus.completeQuotes.values():

    if completeQuoteId % 500 == 0:
        print("Quotation", completeQuoteId, flush=True)

    # each complete quotation needs to have at least one valid quotation
    valid = False
    for lang, quotes in completeQuote.quotes.items():
        for quote in quotes:
            if not quote.about:
                valid = True
                break
        if valid:
            break

    if not valid:
        continue

    completeEntity = completeQuote.entity

    # quotation
    quotationURI = URIRef(QKG) + "Quotation" + str(completeQuoteId)
    completeQuoteId += 1

    # person
    wikidata_id = completeEntity.wikidata_id
    wikidata_id = completeQuote.id.split("_")[0]

    # print("Entity:", wikidata_id)

    if wikidata_id not in existing_quotes:
        existing_quotes[wikidata_id] = dict()

    if wikidata_id not in entity_dict:
        personURI = URIRef(QKG) + "Person" + str(personId)
        person = RDFEntity(personURI)
        person.wikidata_id = wikidata_id
        for lang in completeEntity.wikiquoteIds:
            person.wikiquoteIds[lang] = completeEntity.wikiquoteIds[lang]
            person.labels[lang] = completeEntity.wikiquoteIds[lang]
        for lang in completeEntity.wikiquotePageIds:
            person.wikiquotePageIds[lang] = completeEntity.wikiquotePageIds[lang]
        entity_dict[wikidata_id] = person
        person.types.add("Person")
        personId += 1
    else:
        person = entity_dict[wikidata_id]
        personURI = person.uri
        person.types.add("Person")

    misattributed = False

    date_candidates_with_year = set()
    date_candidates_with_month = set()
    date_candidates_with_day = set()

    found_dates = False
    years = set()
    complete_dates = set()

    for dates in completeQuote.dates:
        for date in dates:
            if date:
                if date == current_date:
                    continue
                if isinstance(date, tuple):
                    if len(date) == 3:
                        complete_dates.add(date)
                    else:
                        years.add(date[0])
                else:
                    years.add(date)
                found_dates = True

    selected_year = None
    selected_date = None
    if found_dates:
        # if there is any conflict: ignore dates
        if len(years) <= 1 and len(complete_dates) <= 1:
            if len(complete_dates) == 0:
                selected_year = years.pop()
            elif len(years) == 0:
                selected_date = complete_dates.pop()
                selected_year = selected_date[0]
            else:
                selected_year = years.pop()
                selected_date = complete_dates.pop()
                if selected_year != selected_date[0]:
                    selected_year = None
                    selected_date = None

    has_quotes = False
    sentiments = []
    for lang, quotes in completeQuote.quotes.items():

        if lang not in all_languages:
            continue

        # translation
        # original

        for quote in quotes:

            if quote.about:
                continue

<<<<<<< HEAD
            if not quote.quote and not quote.original and not quote.translation:
                continue
            
            if quote.quote != None:
                cleaned_text = cleanText(quote.quote)
            elif quote.original:
                cleaned_text = cleanText(quote.original)
            else:
                cleaned_text = cleanText(quote.translation)
=======
            if not quote.quote and not quote.translation:
                continue

            cleaned_text = cleanText(quote.quote)
>>>>>>> 86e7569aea8d50ffd57ca4e3541721839ac5649e

            if not cleaned_text:
                continue

            if cleaned_text.startswith("Citati - "):
                continue

            # check some section titles that were missed before
            section_titles_are_valid = True
            for section_title in quote.section_titles:
                section_title_text = cleanText(section_title)
                if section_title_text in invalid_section_titles:
                    section_titles_are_valid = False
                    break

            if not section_titles_are_valid:
<<<<<<< HEAD
=======
                continue

            if quote.misattributed:
                misattributed = True

            has_quotes = True
            sentiments.append(quote.sentiment[0])

            mentionURI = URIRef(QKG) + "Mention" + str(quotationId)
            quotationId += 1
            g.add((quotationURI, QKG.hasMention, mentionURI))
            g.add((mentionURI, RDF.type, QKG.Mention))
            # text = cleanText(quote.quote, isQuote = True)

            g.add((mentionURI, SO.isPartOf, URIRef(cleanURL("https://" + quote.wikiquote_url))))

            if quote.quote:
                g.add((mentionURI, SO.text, Literal(cleaned_text, lang)))
            # g.add((mentionURI, SO.inLanguage, Literal(lang, datatype=XSD.language)))

            if quote.translation:
                g.add(
                    (mentionURI, SO.text, Literal(cleanText(quote.translation.text), quote.page_language)))
            # g.add((mentionURI, SO.inLanguage, Literal(lang, datatype=XSD.language)))

            if "http" in quote.quote:  # TODO: Remove and do this in pre-processing
>>>>>>> 86e7569aea8d50ffd57ca4e3541721839ac5649e
                continue

            if quote.misattributed:
                misattributed = True

            has_quotes = True
            sentiments.append(quote.sentiment[0])

            mentionURI = URIRef(QKG) + "Mention" + str(quotationId)
            quotationId += 1
            g.add((quotationURI, QKG.hasMention, mentionURI))
            g.add((mentionURI, RDF.type, QKG.Mention))
            # text = cleanText(quote.quote, isQuote = True)

            g.add((mentionURI, SO.isPartOf, URIRef(cleanURL("https://" + quote.wikiquote_url))))

            if quote.quote:
                g.add((mentionURI, SO.text, Literal(cleaned_text, lang)))
                if "http" in quote.quote:  # TODO: Remove and do this in pre-processing
                    continue
            if quote.original:
                g.add((mentionURI, SO.text, Literal(cleaned_text, lang)))
                if "http" in quote.original:  # TODO: Remove and do this in pre-processing
                    continue
            
            # g.add((mentionURI, SO.inLanguage, Literal(lang, datatype=XSD.language)))


            if quote.translation and (quote.quote or quote.original):
                g.add(
                    (mentionURI, SO.text, Literal(cleanText(quote.translation), quote.page_language)))
            # g.add((mentionURI, SO.inLanguage, Literal(lang, datatype=XSD.language)))

            
            # linked entities
            if quote.entities:
                for entity in quote.entities:

                    entity_wikidata_id = entity.wikidata_id
                    if not entity_wikidata_id and entity.wikiquote_id and entity.wikiquote_id in \
                            wikiquote_to_wikidata_mapping[quote.page_language]:
                        entity_wikidata_id = wikiquote_to_wikidata_mapping[quote.page_language][entity.wikiquote_id]

                    if entity_wikidata_id:
                        if entity_wikidata_id not in entity_dict:
                            if "Person" in entity.types:
                                entityURI = URIRef(QKG) + "Person" + str(personId)
                                personId += 1
                            else:
                                entityURI = URIRef(QKG) + "Entity" + str(entityId)
                                entityId += 1
                            rdf_entity = RDFEntity(entityURI)
                            rdf_entity.wikidata_id = entity_wikidata_id
                            entity_dict[entity_wikidata_id] = rdf_entity
                        else:
                            rdf_entity = entity_dict[entity_wikidata_id]

                        rdf_entity.wikiquoteIds[quote.page_language] = entity.wikiquote_id
                        rdf_entity.labels[quote.page_language] = entity.wikiquote_id
                        for entity_type in entity.types:
                            rdf_entity.types.add(entity_type)

                        g.add((quotationURI, SO.mentions, rdf_entity.uri))

            if quote.footnotes:
                for footnote in quote.footnotes:  # footnotes are text-only contexts
                    text = cleanText(footnote)
                    if text:
                        contextURI = URIRef(QKG) + "Context" + str(contextId)
                        g.add((contextURI, RDF.type, QKG.Context))
                        g.add((contextURI, QKG.contextText, Literal(text, quote.page_language)))
                        # g.add((contextURI, SO.inLanguage, Literal(quote.page_language, datatype=XSD.language)))
                        g.add((mentionURI, QKG.hasContext, contextURI))
                        contextId += 1
<<<<<<< HEAD
            if quote.quote:
                text = quote.quote
            elif quote.original:
                text = quote.original
            else:
                text = quote.translation
=======

            text = quote.quote
>>>>>>> 86e7569aea8d50ffd57ca4e3541721839ac5649e
            if lang not in existing_quotes[completeEntity.wikidata_id]:
                existing_quotes[completeEntity.wikidata_id][lang] = set()

            if text in existing_quotes[completeEntity.wikidata_id][
                lang]:  # Remove duplicates. TODO: Which of the duplicates to keep? What if quotation is empty?
                continue

            existing_quotes[completeEntity.wikidata_id][lang].add(text)

            # print(quote.section_titles) # TODO: Section titles
            for section_title in quote.section_titles:
                section_title_text = cleanText(section_title)
                if section_title_text:
                    if len(section_title_text) >= 3 and section_title_text != 'Quotes':
                        if quote.page_language not in person.wikiquoteIds or person.wikiquoteIds[
                            quote.page_language] != section_title_text:
                            g.add((mentionURI, SO.description, Literal(section_title_text, quote.page_language)))

            if quote.contexts:
                for context in quote.contexts:
                    contextURI = URIRef(QKG) + "Context" + str(contextId)

                    text = context.text

                    g.add((contextURI, RDF.type, QKG.Context))
                    g.add((mentionURI, QKG.hasContext, contextURI))
                    if text:
                        g.add((contextURI, QKG.contextText, Literal(text, quote.page_language)))
                    # g.add((contextURI, SO.inLanguage, Literal(quote.page_language, datatype=XSD.language)))

                    contextId += 1
                    for external_link in context.external_links:
                        g.add((contextURI, SO.source, URIRef(cleanURL(external_link.uri))))
                    for entity in context.entities:

                        # TODO: Deduplicate with code above (problem: uses some global variables such as personId)

                        entity_wikidata_id = entity.wikidata_id
                        if not entity_wikidata_id and entity.wikiquote_id and entity.wikiquote_id in \
                                wikiquote_to_wikidata_mapping[quote.page_language]:
                            entity_wikidata_id = wikiquote_to_wikidata_mapping[quote.page_language][entity.wikiquote_id]

                        if entity_wikidata_id:
                            if entity_wikidata_id not in entity_dict:
                                if "Person" in entity.types:
                                    entityURI = URIRef(QKG) + "Person" + str(personId)
                                    personId += 1
                                else:
                                    entityURI = URIRef(QKG) + "Entity" + str(entityId)
                                    entityId += 1
                                rdf_entity = RDFEntity(entityURI)
                                rdf_entity.wikidata_id = entity_wikidata_id
                                entity_dict[entity_wikidata_id] = rdf_entity
                            else:
                                rdf_entity = entity_dict[entity_wikidata_id]

                            rdf_entity.wikiquoteIds[quote.page_language] = entity.wikiquote_id
                            rdf_entity.labels[quote.page_language] = entity.wikiquote_id
                            for entity_type in entity.types:
                                rdf_entity.types.add(entity_type)

                            g.add((contextURI, QKG.mentions, rdf_entity.uri))

            if quote.source or quote.comment or quote.explanation or quote.notes or quote.title:
                contextURI = URIRef(QKG) + "Context" + str(contextId)
                contextId += 1

                # addTemplateContext()

                if quote.source:
                    processTemplateContext(g, quote.source, contextURI, quote.page_language)

                if quote.comment:
                    processTemplateContext(g, quote.comment, contextURI, quote.page_language)

                if quote.explanation:
                    processTemplateContext(g, quote.explanation, contextURI, quote.page_language)

                if quote.notes:
                    processTemplateContext(g, quote.notes, contextURI, quote.page_language)

                if quote.title:
                    processTemplateContext(g, quote.title, contextURI, quote.page_language)

                g.add((contextURI, RDF.type, QKG.Context))
                g.add((mentionURI, QKG.hasContext, contextURI))

    # if found_dates:
    #    print("")

    if not has_quotes:
        continue

    if selected_date:
        date_string = createDateString(selected_date)
        if date_string:
            g.add((quotationURI, SO.dateCreated, Literal(date_string, datatype=XSD.date)))
    if selected_year:
        g.add((quotationURI, DBO.year, Literal(str(selected_year), datatype=XSD.gYear)))

    g.add((quotationURI, RDF.type, SO.Quotation))
    g.add((quotationURI, SO.spokenByCharacter, personURI))

    # Sentiment
    # print("Sentiments:", sentiments)
    sentiment = aggregateSentiment(sentiments)
    # print("Aggregated sentiment:", sentiment)

    emotionSetURI = URIRef(QKG) + "EmotionSet" + str(emotionSetId)
    g.add((emotionSetURI, RDF.type, ONYX.EmotionSet))
    emotionURI = URIRef(QKG) + "Emotion" + str(emotionId)
    g.add((emotionURI, RDF.type, ONYX.Emotion))
    emotionSetId += 1
    emotionId += 1

    g.add((quotationURI, ONYX.hasEmotionSet, emotionSetURI))
    g.add((emotionSetURI, ONYX.hasEmotion, emotionURI))
    g.add((emotionURI, ONYX.hasEmotionIntensity, Literal(sentiment["score"], datatype=XSD.float)))
    g.add((emotionURI, ONYX.hasEmotionCategory, emotionCategoryDict[sentiment["label"]]))

    g.add((quotationURI, QKG.isMisattributed, Literal(misattributed, datatype=XSD.boolean)))

    # if completeQuoteId > 1000:
    #    break

print("Open Wikidata->DBpedia mapping")

wikidata_to_dbpedia = dict()
used_wikidata_ids = entity_dict.keys()
wikidata_to_dbpedia_file = open("sameas-all-wikis.csv")
for line in wikidata_to_dbpedia_file:
    wikidata_id, dbpedia_id = line.split()
    if wikidata_id in used_wikidata_ids:
        if wikidata_id not in wikidata_to_dbpedia:
            wikidata_to_dbpedia[wikidata_id] = dict()
        if dbpedia_id.startswith("http://dbpedia.org/resource/"):  # English
            wikidata_to_dbpedia[wikidata_id]["en"] = dbpedia_id
        else:
            for lang in languages:
                if dbpedia_id.startswith("http://" + lang + ".dbpedia.org/resource/"):
                    wikidata_to_dbpedia[wikidata_id][lang] = dbpedia_id

print("Create entity triples", flush=True)
for entity in entity_dict.values():
    if "Person" in entity.types:
        g.add((entity.uri, RDF.type, SO.Person))
    for entity_type in entity.types:
        g.add((entity.uri, RDF.type, URIRef(DBO) + entity_type))
    g.add((entity.uri, OWL.sameAs, URIRef(WD) + entity.wikidata_id))
    # for lang, wikiquotePageId in entity.wikiquotePageIds.items():
    #    g.add((entity.uri, OWL.sameAs, wqCurid[lang] + str(wikiquotePageId)))
    for lang, wikiquoteId in entity.wikiquoteIds.items():
        #g.add((entity.uri, OWL.sameAs, wq[lang] + requests.utils.quote(wikiquoteId)))
        g.add((entity.uri, OWL.sameAs, URIRef(wq[lang] + wikiquoteId.replace(" ","_"))))
        g.add((entity.uri, RDFS.label, Literal(wikiquoteId, lang)))

    dbpedia_labels = dict()
    if entity.wikidata_id in wikidata_to_dbpedia:
        for lang in wikidata_to_dbpedia[entity.wikidata_id]:
            dbpedia_url = wikidata_to_dbpedia[entity.wikidata_id][lang]
            dbpedia_label = dbpedia_url.rsplit('/', 1)[-1].replace("_", " ")
            g.add((entity.uri, OWL.sameAs, URIRef(dbpedia_url)))
            g.add((entity.uri, RDFS.label, Literal(dbpedia_label, lang)))
            dbpedia_labels[lang] = dbpedia_label

    # Take the label of the most prioritised language
    for lang in languages:
        if lang in entity.wikiquoteIds:
            label = entity.wikiquoteIds[lang]
            break
        if lang in dbpedia_labels:
            label = dbpedia_labels[lang]
            break
    if label:
        g.add((entity.uri, SKOS.prefLabel, Literal(label)))

print("Write file", flush=True)
filename = "quotekg.ttl"
# file = open(filename, "w")
# file.write(g.serialize(format='ttl').decode("utf-8"))
# file.close()
g.serialize(destination=filename, format="ttl")

# fix rdflib issue https://github.com/RDFLib/rdflib/issues/747
print("Fix gYear bug", flush=True)
path = Path(filename)
text = path.read_text()
text = text.replace('-01-01"^^xsd:gYear', '"^^xsd:gYear')
path.write_text(text)

print("Done")
