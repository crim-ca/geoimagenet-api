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
                script {
                    docker.image('kartoza/postgis:9.6-2.4').withRun('-e "ALLOW_IP_RANGE=0.0.0.0/0" -e "IP_LIST=*" -e "POSTGRES_USER=docker" -e "POSTGRES_PASS=docker"') { c ->
                        sh """
                        docker run --rm --link ${c.id}:postgis geoimagenet_api /bin/sh -c \" \
                        pip install -r requirements_dev.txt && \
                        pytest -v\"
                        """
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying...'
            }
        }
    }
}