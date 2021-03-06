"""Simplifies the execution of the src scripts.

Provides options to create database and run model pipeline.

"""

import argparse
import logging.config

import pandas as pd
import yaml

from config.flaskconfig import SQLALCHEMY_DATABASE_URI
from src import model
from src.database import create_db
from src.clean import remove_outliers, drop_empty_content, drop_non_en_content
from src.process import process_data
from src.read import read_data, combine_data

logging.config.fileConfig('config/logging/local.conf', disable_existing_loggers=False)
logger = logging.getLogger('tweets-pipeline')

if __name__ == '__main__':
    # Add parsers for creating a database and adding tweets to it
    parser = argparse.ArgumentParser(description="Creating database and running model pipeline")
    subparsers = parser.add_subparsers(dest='subparser_name')

    # Sub-parser for creating a database
    sb_create = subparsers.add_parser('create_db', description='Create database')
    sb_create.add_argument('--engine_string', default=SQLALCHEMY_DATABASE_URI,
                           help='SQLAlchemy connection URI for database')

    # Sub-parser for model pipeline
    sb_pipeline = subparsers.add_parser('pipeline', description='Run model pipeline')
    sb_pipeline.add_argument('step', help='Which step to run',
                             choices=['read', 'process', 'clean', 'train'])
    sb_pipeline.add_argument('--config', default='config/config.yaml',
                             help='Path to configuration file')
    sb_pipeline.add_argument('--input', '-i', default=None,
                             help='Path to input data')
    sb_pipeline.add_argument('--output', '-o', default=None,
                             help='Path to save output CSV (optional, default=None)')

    # Interpret and execute commands
    args = parser.parse_args()
    sp_used = args.subparser_name

    if sp_used == 'create_db':
        create_db(args.engine_string)

    elif sp_used == "pipeline":
        # Load configuration file for parameters
        try:
            with open(args.config, "r") as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
            logger.info("Configuration file loaded from %s", args.config)
        except FileNotFoundError:
            logger.error("Cannot find configuration file from the path: %s", args.config)

        # Read input csv into a DataFrame
        if args.input is not None:
            input = pd.read_csv(args.input)
            logger.info('Input data loaded from %s', args.input)

        # Interpret and execute commands
        if args.step == 'read':
            df1 = read_data(**config['read']['read_data']['file1'])
            df2 = read_data(**config['read']['read_data']['file2'])
            output = combine_data(df1, df2, **config['read']['combine_data'])
        elif args.step == 'process':
            output = process_data(input, **config['process']['process_data'])
        elif args.step == 'clean':
            df = remove_outliers(input, **config['clean']['remove_outliers'])
            df = drop_empty_content(df, **config['clean']['drop_empty_content'])
            output = drop_non_en_content(df, **config['clean']['drop_non_en_content'])
        elif args.step == 'train':
            model.set_seed(**config['model']['set_seed'])
            train_contents, test_contents, train_labels, test_labels = model.train_test_split(
                input, **config['model']['train_test_split'])
            vocab_size = model.fit_tokenizer(train_contents, **config['model']['fit_tokenizer'])
            train_data = model.tokenize(train_contents, **config['model']['tokenize'])
            test_data = model.tokenize(test_contents, **config['model']['tokenize'])
            lstm_model = model.compile_model(vocab_size, **config['model']['compile_model'])
            model.fit_model(lstm_model, train_data, train_labels, **config['model']['fit_model'])
            model.calculate_mape(test_data, test_labels, **config['model']['calculate_mape'])

        # Save output DataFrame to a csv
        if args.output is not None:
            output.to_csv(args.output, index=False)
            logger.info("Output saved to %s" % args.output)

    else:
        parser.print_help()
