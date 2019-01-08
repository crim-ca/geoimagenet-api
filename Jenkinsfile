#!/usr/bin/env groovy

pipeline {
    agent any

    options {
        buildDiscarder (logRotator(numToKeepStr:'10'))
    }

    stages {

        stage('Build') {
            steps {
                sh 'docker build -t docker-registry.crim.ca/geoimagenet/api:latest .'
            }
        }

        stage('Test') {
            steps {
                script {
                    docker.image('kartoza/postgis:9.6-2.4').withRun('-e "ALLOW_IP_RANGE=0.0.0.0/0" -e "IP_LIST=*" -e "POSTGRES_USER=docker" -e "POSTGRES_PASS=docker"') { c ->
                        sh """
                        docker run --rm --link ${c.id}:postgis -e GEOIMAGENET_API_POSTGIS_USER=docker -e GEOIMAGENET_API_POSTGIS_PASSWORD=docker -e GEOIMAGENET_API_POSTGIS_HOST=postgis docker-registry.crim.ca/geoimagenet/api:latest /bin/sh -c \" \
                        pip install -r requirements_dev.txt && \
                        pytest -v\"
                        """
                    }
                }
            }
        }

        stage('Push Docker Image') {
            when {
                branch 'jenkins'
            }
            steps {
                withDockerRegistry([ credentialsId: "docker-registry-caronda", url: "https://docker-registry.crim.ca/" ]) {
                  sh 'docker push docker-registry.crim.ca/geoimagenet/api:latest'
                }
            }
        }
    }
}