// Jenkinsfile — csv-records-api
// GitHub -> Jenkins -> pytest -> Docker build -> Docker Hub -> Minikube -> API tests
//
// Jenkins credentials required (Manage Jenkins -> Credentials):
//   dockerhub-creds      Username with password  (Docker Hub user + access token)
//   kubeconfig-minikube  Secret file             (kubeconfig pointing at https://<minikube ip>:8443)

pipeline {
    agent any

    parameters {
        choice(name: 'DEPLOY_MODE', choices: ['manual', 'auto'],
               description: 'manual = wait for your approval before deploying to Minikube; auto = deploy straight away')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
    }

    triggers {
        // Jenkins on a laptop can't receive GitHub webhooks, so poll the repo every ~2 minutes
        pollSCM('H/2 * * * *')
    }

    environment {
        DOCKERHUB_USER = 'saket123'          // <-- change this
        APP_NAME       = 'csv-records-api'
        IMAGE          = "docker.io/${DOCKERHUB_USER}/${APP_NAME}"
        K8S_NAMESPACE  = 'csv-api'
        NODE_PORT      = '30080'
    }

    stages {
        stage('Prepare') {
            steps {
                script {
                    env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "jenkins-${env.BUILD_NUMBER}-${env.GIT_SHORT}"
                }
                echo "Commit ${env.GIT_SHORT} -> image ${env.IMAGE}:${env.IMAGE_TAG}"
                sh 'docker version --format "Docker {{.Server.Version}}" && kubectl version --client'
            }
        }

        stage('Test (pytest)') {
            steps {
                // Runs pytest inside the "test" stage of our Dockerfile (Python 3.12, same as CI)
                sh 'docker build --target test -t ${APP_NAME}:test-${BUILD_NUMBER} .'
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target runtime \
                      --label org.opencontainers.image.revision=${GIT_SHORT} \
                      -t ${IMAGE}:${IMAGE_TAG} \
                      -t ${IMAGE}:jenkins-latest .
                '''
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push ${IMAGE}:${IMAGE_TAG}
                        docker push ${IMAGE}:jenkins-latest
                    '''
                }
            }
            post {
                always { sh 'docker logout || true' }
            }
        }

        stage('Approve Deploy') {
            // Anything other than "auto" (including the very first build, before parameters exist) waits here
            when { expression { params.DEPLOY_MODE != 'auto' } }
            options { timeout(time: 15, unit: 'MINUTES') }
            steps {
                input message: "Deploy ${env.IMAGE}:${env.IMAGE_TAG} to Minikube?", ok: 'Deploy'
            }
        }

        stage('Deploy to Minikube') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl apply -f k8s/namespace.yaml
                        kubectl apply -f k8s/configmap.yaml -f k8s/service.yaml
                        # Swap the image tag in the Deployment for the one we just pushed
                        sed "s#image: .*${APP_NAME}:.*#image: ${IMAGE}:${IMAGE_TAG}#" k8s/deployment.yaml \
                          | kubectl apply -f -
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/${APP_NAME} --timeout=180s
                        kubectl -n ${K8S_NAMESPACE} get deploy,pods,svc -o wide
                    '''
                }
            }
        }

        stage('API Test') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                    sh '''
                        set -e
                        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
                        BASE="http://${NODE_IP}:${NODE_PORT}"
                        echo "Testing ${BASE}"

                        for i in $(seq 1 30); do
                          curl -fsS "${BASE}/health" > /dev/null && break
                          [ "$i" -eq 30 ] && { echo "API not reachable"; exit 1; }
                          sleep 2
                        done

                        curl -fsS "${BASE}/health"        | jq -e '.status == "ok"'
                        curl -fsS "${BASE}/records"       | jq -e '.total > 0'
                        curl -fsS "${BASE}/records/1"     | jq -e '.id == 1'
                        curl -fsS "${BASE}/records/stats" | jq -e '.total_records > 0'

                        code=$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/records/999999")
                        [ "$code" = "404" ] || { echo "Expected 404, got $code"; exit 1; }

                        echo "All API tests passed"
                    '''
                }
            }
            post {
                failure {
                    // Bad release? Roll back to the previous ReplicaSet automatically
                    withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
                        sh 'kubectl -n ${K8S_NAMESPACE} rollout undo deployment/${APP_NAME} || true'
                    }
                }
            }
        }
    }

    post {
        always {
            // Clean up local images (the pushed ones live on Docker Hub)
            sh 'docker rmi ${APP_NAME}:test-${BUILD_NUMBER} ${IMAGE}:${IMAGE_TAG} ${IMAGE}:jenkins-latest 2>/dev/null || true'
        }
        success {
            echo "Deployed ${env.IMAGE}:${env.IMAGE_TAG} to Minikube (namespace ${env.K8S_NAMESPACE})"
        }
    }
}
