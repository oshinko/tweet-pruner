# Tweet Pruner

Prune junk tweets and clean up your Twitter (X.com) history.

## Prerequisites

1. First, [download your archive](https://help.x.com/en/managing-your-account/how-to-download-your-x-archive)
1. Register your application
    1. Go to the [X Developer Portal](https://developer.x.com/) and log in with your account
    1. Create a new application and obtain your **Client ID** and **Client Secret**
    1. Set the **Redirect URI** to `http://localhost:8000/authorized` or your desired callback URL
    1. Update your `.env` file with these values
1. Extract the `.zip` file and place the `tweets.json` file into the `data/`

## Setup

1. Copy the environment file template and make necessary edits:

    ```sh
    cp template.env .env  # Edit this file with your API keys and configuration
    ```

1. Start the services using Docker:

    ```sh
    docker compose up -d
    ```

1. Go to `http://localhost:8000/` to initiate authentication

This will start the Tweet Pruner server and begin processing the tweets based on the configuration in `.env`.
