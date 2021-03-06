#!/usr/bin/env Rscript

## Diff two .qsf translation files to find new and changed survey items
##
## Usage:
##
## Rscript translation-differ.R path/to/old/qsf path/to/new/qsf
##
## Writes the lists of new and changed items to STDOUT, so redirect STDOUT to
## your desired location.


#### Background on .qsf files

## A .qsf file is a json containing two elements, SurveyEntry with survey
## metadata (start date, ID, name, etc) and SurveyElements with a numbered list
## of survey components. For the purpose of finding differences in survey
## contents, we are only interested in examining the SurveyElements item.

## SurveyElement types are BL (block), FL (flow), SO (survey options), SCO
## (scoring), PROJ (?), notes, STAT (statistics), QC (question count), SQ
## (survey questions), and RS (response set). Detailed info:
## https://gist.github.com/ctesta01/d4255959dace01431fb90618d1e8c241

## We are only interested in block information ("BL") and survey questions
## ("SQ"). The single BL item lists questions that appear in each block. The
## "Trash" block contains not-displayed items. Within each SQ item, details are
## stored in the Payload element, which can contain the following fields:

# [1] "QuestionText"         "QuestionType"         "Selector"             "Configuration"        "QuestionDescription"  "Choices"              "ChoiceOrder"         
# [8] "Validation"           "AnalyzeChoices"       "Language"             "QuestionText_Unsafe"  "DataExportTag"        "QuestionID"           "DataVisibility"      
# [15] "NextChoiceId"         "NextAnswerId"         "DefaultChoices"       "SubSelector"          "DisplayLogic"         "GradingData"          "Answers"             
# [22] "AnswerOrder"          "ChoiceDataExportTags" "Randomization"        "RecodeValues"         "DynamicChoices"       "DynamicChoicesData"   "SearchSource"        
# [29] "QuestionJS"  

## The meaning of "Answers" and "Choices" differs for matrix vs non-matrix
## items. "Choices" list the vertical components -- subquestions for matrix
## items and answer choices for non-matrix items. "Answers" list the answer
## choices for matrix items and are missing for non-matrix items.


suppressPackageStartupMessages({
  library(jsonlite)
  library(stringr)
})

#' Load and diff chosen translation files.
#'
#' @param old_qsf_path path to older Qualtrics translation file in .qsf format
#' @param new_qsf_path path to newer Qualtrics translation file in .qsf format
diff_qsf_files <- function(old_qsf_path, new_qsf_path) {
  old_qsf <- get_qsf_file(old_qsf_path)
  new_qsf <- get_qsf_file(new_qsf_path)
  
  diff_surveys(old_qsf, new_qsf)
  
  return(NULL)
}

#' Fetch and format a single .qsf translation file, keeping block and question info
#'
#' @param path path to Qualtrics translation file in .qsf format
#'
#' @return A named list
get_qsf_file <- function(path) {
  # Read file as json.
  qsf <- read_json(path)
  
  ## Block
  block_out <- Filter(function(elem) { elem[["Element"]] == "BL" }, qsf$SurveyElements)[[1]]$Payload
  
  shown_items <- list()
  for (block in block_out) {
    if (block$Type == "Trash") {
      next
    }
    
    shown_items[[block$Description]] <- sapply(
      block$BlockElements, function(elem) {
        if (elem$Type == "Question") { elem$QuestionID }
      })
  }
  shown_items <- unlist(shown_items)
  
  ## Questions
  keep_items <- c("QuestionID", "DataExportTag", "QuestionText",
                  "QuestionType", "Choices", "Answers", "DisplayLogic")
  questions <- Filter(function(elem) { elem[["Element"]] == "SQ" }, qsf$SurveyElements)
  
  qid_item_map <- list()
  questions_out <- list()
  for (question in questions) {
    question <- question$Payload
    
    # Skip items not shown to respondents.
    if ( !(question$QuestionID %in% shown_items) ) {
      next
    }
    
    question <- question[names(question) %in% keep_items]
    
    # Rearrange Answers/Choices elements to be consistent between matrix and
    # other items.
    if (question$QuestionType == "Matrix") {
      question$Subquestions <- question$Choices
      question$Choices <- question$Answers
      question$Answers <- NULL
    }
    
    # DisplayLogic "Description" summarizes display logic, including the text of
    # the conditioning question. We don't want to detect changes in conditioning
    # question text if the QID stayed the same, so keep only fields not named
    # "Description".
    display_logic <- unlist(question$DisplayLogic)
    question$DisplayLogic <- sort(display_logic[!str_detect(names(display_logic), "Description")])
    
    questions_out <- safe_insert_question(questions_out, question)
    qid_item_map[[question$QuestionID]] <- question$DataExportTag
  }
  
  qid_item_map <- unlist(qid_item_map)
  shown_items <- qid_item_map[shown_items]
  
  return(list(questions=questions_out, shown_items=shown_items))
}

#' Insert new question data into list without overwriting item of the same name
#'
#' @param question_list named list storing a collection of questions
#' @param question named list storing data for a single trimmed question from `get_qsf_file`
#'
#' @return The modified questions_list object
safe_insert_question <- function(questions_list, question) {
  if ( !is.null(questions_list[[question$DataExportTag]]) ) {
    old_qid <- questions_list[[question$DataExportTag]]$QuestionID
    new_qid <- question$QuestionID
    
    stop(paste0("Multiple copies of item ", question$DataExportTag, " exist, ", old_qid, " and ", new_qid))
  }
  
  questions_list[[question$DataExportTag]] <- question
  return(questions_list)
}

#' Compare the two surveys.
#'
#' @param old_qsf named list of trimmed output from `get_qsf_file` for older survey
#' @param new_qsf named list of trimmed output from `get_qsf_file` for newer survey
diff_surveys <- function(old_qsf, new_qsf) {
  ## Diff blocks
  old_shown_items <- old_qsf$shown_items
  new_shown_items <- new_qsf$shown_items
  old_questions <- old_qsf$questions
  new_questions <- new_qsf$questions
  
  added <- setdiff(new_shown_items, old_shown_items)
  removed <- setdiff(old_shown_items, new_shown_items)
  
  print_questions(added, "Added", new_questions)
  print_questions(removed, "Removed", old_questions)
  
  ## For questions that appear in both surveys, check for changes in wording,
  ## display logic, and answer options.
  shared <- intersect(old_shown_items, new_shown_items)
  
  diff_question(shared, "QuestionText", old_questions, new_questions)
  diff_question(shared, "DisplayLogic", old_questions, new_questions)
  diff_question(shared, "Choices", old_questions, new_questions)
  diff_question(shared, "Subquestions", old_questions, new_questions)
  
  return(NULL)
}

#' Compare a single question field in the two surveys.
#'
#' @param names character vector of Qualtrics question IDs
#' @param change_type character; type of change to look for and name of question
#'   element to compare between survey versions
#' @param old_qsf named list of trimmed output from `get_qsf_file` for older
#'   survey
#' @param new_qsf named list of trimmed output from `get_qsf_file` for newer
#'   survey
diff_question <- function(names, change_type=c("Choices", "QuestionText", "DisplayLogic", "Subquestions"), old_qsf, new_qsf) {
  change_type <- match.arg(change_type)
  
  changed <- c()
  for (question in names) {
    if ( !identical(old_qsf[[question]][[change_type]], new_qsf[[question]][[change_type]]) ) {
      changed <- append(changed, question)
    }
  }
  print_questions(changed, change_type, new_qsf)
  
  return(NULL)
}

#' Print results with custom message for each possible change type.
#'
#' @param questions character vector of Qualtrics question IDs for items that
#'   changed between survey versions
#' @param change_type character; type of change to look for
#' @param reference_qsf named list of trimmed output from `get_qsf_file` for survey that
#'   contains descriptive info about a particular type of change. For "removed"
#'   questions, should be older survey, else newer survey.
print_questions <- function(questions, change_type=c("Added", "Removed", "Choices", "QuestionText", "DisplayLogic", "Subquestions"), reference_qsf) {
  if ( length(questions) > 0 ) {
    change_type <- match.arg(change_type)
    
    text_options <- list(
      Added = "Added: item %s (%s)\n",
      Removed = "Removed: item %s (%s)\n",
      QuestionText = "Question wording changed: item %s (%s)\n",
      DisplayLogic = "Display logic changed: item %s (%s)\n",
      Choices = "Answer choices changed: item %s (%s)\n",
      Subquestions = "Matrix subquestions changed: item %s (%s)\n"
    )
    
    questions <- sort(questions)
    qids <- sapply(questions, function(question) { reference_qsf[[question]]$QuestionID })
    
    cat("\n ")
    cat(sprintf(text_options[[change_type]], questions, qids))
  }
  return(NULL)
}



args <- commandArgs(TRUE)

if (length(args) != 2) {
  stop("Usage: Rscript translation-differ.R path/to/old/qsf path/to/new/qsf")
}

old_qsf <- args[1]
new_qsf <- args[2]

invisible(diff_qsf_files(old_qsf, new_qsf))
