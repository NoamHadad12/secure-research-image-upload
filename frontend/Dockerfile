FROM node:24.11.1-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY . ./

EXPOSE 5173

CMD ["npm", "run", "dev"]
