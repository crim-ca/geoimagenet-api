#!/usr/bin/env groovy

pipeline {
    agent any

    environment {
        TAG_NAME = sh(returnStdout: true, script: '[[ -z $(git tag -l --points-at HEAD) ]] && printf latest || printf $(git tag -l --points-at HEAD)')
        LOCAL_IMAGE_NAME = "geoimagenet_api:$TAG_NAME"
        LATEST_IMAGE_NAME = "docker-registry.crim.ca/geoimagenet/api:latest"
        TAGGED_IMAGE_NAME = "docker-registry.crim.ca/geoimagenet/api:$TAG_NAME"
    }

    options {
        buildDiscarder (logRotator(numToKeepStr:'10'))
    }

    stages {

        stage('Build') {
            steps {
                sh 'env | sort'
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
                        pytest --cov > coverage.out\"
                        """
                    }
                }
            }
        }

        stage('Deploy') {
            when {
                environment name: 'GIT_LOCAL_BRANCH', value: 'release'
            }
            steps {
                sh 'docker tag $LOCAL_IMAGE_NAME $TAGGED_IMAGE_NAME'
                sh 'docker push $TAGGED_IMAGE_NAME'
                sh 'docker tag $LOCAL_IMAGE_NAME $LATEST_IMAGE_NAME'
                sh 'docker push $LATEST_IMAGE_NAME'
                sh 'ssh ubuntu@geoimagenetdev.crim.ca "cd ~/compose && ./geoimagenet-compose.sh pull api && ./geoimagenet-compose.sh up --force-recreate -d api"'
                slackSend channel: '#jenkins-debug', color: 'good', message: "*GeoImageNet API*:\nPushed docker image: `${env.TAGGED_IMAGE_NAME}`\nDeployed to: https://geoimagenetdev.crim.ca/api/v1"
            }
        }
        // stage('Clean') {
            // Use this command to clean all geoimagenet images on jenkins
        //     sh 'docker rmi $(docker images --format "{{.ID}}: {{.Repository}}" | grep geoimagenet | cut -c 1-12)'
        // }
    }
    post {
       success {
           slackSend channel: '#jenkins-debug',
                     color: 'good',
                     message: "*GeoImageNet API*: Build #${env.BUILD_NUMBER} *successful* on git branch `${env.GIT_LOCAL_BRANCH}` :tada: (<${env.BUILD_URL}|View>) (Test coverage: `cat coverage.out | grep TOTAL | sed -r 's/.+ ([0-9]+%)/\1/'`)"
       }
       failure {
           slackSend channel: '#jenkins-debug', color: 'danger', message: "*GeoImageNet API*: Build #${env.BUILD_NUMBER} *failed* on git branch `${env.GIT_LOCAL_BRANCH}` :sweat_smile: (<${env.BUILD_URL}|View>)"
       }
    }
}