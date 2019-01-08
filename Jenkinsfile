#!/usr/bin/env groovy

pipeline {
    agent any

    options {
        buildDiscarder (logRotator(numToKeepStr:'10'))
    }

    stages {

        stage('Build') {
            steps {
                sh 'docker build -t geoimagenet_api .'
            }
        }

        stage('Test') {
            steps {
                echo 'Testing...'
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying...'
            }
        }
    }
}