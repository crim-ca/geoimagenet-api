#!/usr/bin/env groovy

pipeline {
    agent any

    environment {
        TAG_NAME = sh(returnStdout: true, script: 'git tag -l --points-at HEAD')
        LOCAL_IMAGE_NAME = "geoimagenet_api:$TAG_NAME"
        IMAGE_NAME = "docker-registry.crim.ca/geoimagenet/api:${TAG_NAME}"
    }

    options {
        buildDiscarder (logRotator(numToKeepStr:'10'))
    }

    stages {

        stage('Build') {
            steps {
                sh 'docker build -t $LOCAL_IMAGE_NAME .'
            }
        }

        stage('Test') {
            steps {
                script {
                    docker.image('kartoza/postgis:9.6-2.4').withRun('-e "ALLOW_IP_RANGE=0.0.0.0/0" -e "IP_LIST=*" -e "POSTGRES_USER=docker" -e "POSTGRES_PASS=docker"') { c ->
                        sh """
                        docker run --rm --link ${c.id}:postgis -e GEOIMAGENET_API_POSTGIS_USER=docker -e GEOIMAGENET_API_POSTGIS_PASSWORD=docker -e GEOIMAGENET_API_POSTGIS_HOST=postgis $LOCAL_IMAGE_NAME /bin/sh -c \" \
                        pip install -r requirements_dev.txt && \
                        pytest -v\"
                        """
                    }
                }
            }
        }

        stage('Push Docker Image') {
            when {
                environment name: 'GIT_LOCAL_BRANCH', value: 'master'
            }
            steps {
                sh 'docker tag $LOCAL_IMAGE_NAME $IMAGE_NAME'
                sh 'docker push $IMAGE_NAME'
            }
        }
    }
}