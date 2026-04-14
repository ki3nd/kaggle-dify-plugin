# Privacy Policy

## Data Collection

This plugin does not collect, store, or transmit any personal data on its own.

## Credentials

Your Kaggle API token is entered once in Dify's credential store. It is used solely to authenticate requests to the Kaggle API on your behalf and is never logged or shared with any third party.

## Data Sent to Kaggle

When you use this plugin, the following data is sent directly to the [Kaggle API](https://www.kaggle.com/docs/api):

- Your API token (for authentication)
- Kernel identifiers and code you provide as tool inputs
- File path parameters used to retrieve output files

All data handling on Kaggle's side is governed by the [Kaggle Privacy Policy](https://www.kaggle.com/privacy).

## Local Storage

Temporary files (kernel output, downloaded files) are written to a `temp/` directory during tool execution and deleted immediately after the response is returned.

## Contact

For questions or concerns, open an issue at [https://github.com/ki3nd/kaggle-dify-plugin/issues](https://github.com/ki3nd/kaggle-dify-plugin/issues).
