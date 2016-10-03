doi-resolution-report
=====================

DataCite resolution reports

Builds DOI resolution reports from CNRI logs.

`python report.py input_directory/ output_directory/`

- The input_directory will be searched recursively for %s files.
- The input_directory can be e.g /home/cnri. For each directory containing files a report will be created. The name of the report will be based on the directory name.
- The output_directory must exist. The files in the output directory will be overwritten.
